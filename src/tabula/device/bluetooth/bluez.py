from __future__ import annotations

import abc
import collections
import collections.abc
import contextlib
import logging
import re
import textwrap
import typing
import weakref

import outcome
import tricycle
import trio
import trio._repl
import trio.lowlevel
from jeepney.bus_messages import MatchRule, message_bus
from jeepney.io.common import RouterClosed, check_replyable
from jeepney.io.trio import DBusConnection, open_dbus_connection
from jeepney.low_level import HeaderFields, Message, MessageFlag, MessageType
from jeepney.wrappers import DBusAddress, DBusErrorResponse, new_error, new_method_call, new_method_return, new_signal

logger = logging.getLogger(__name__)

UNIQUE_NAME_P = re.compile(r":[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)$")
WELL_KNOWN_NAME_P = re.compile(r"([A-Za-z_-][A-Za-z0-9_-]*(\.[A-Za-z_-][A-Za-z0-9_-]*)+)$")

UniqueName = typing.NewType("UniqueName", str)
WellKnownName = typing.NewType("WellKnownName", str)

type BusName = UniqueName | WellKnownName
ObjectPath = typing.NewType("ObjectPath", str)
InterfaceName = typing.NewType("InterfaceName", str)

PropertyName = typing.NewType("PropertyName", str)
Signature = typing.NewType("Signature", str)

Signal = typing.NewType("Signal", Message)

BUS_WNK = WellKnownName("org.freedesktop.DBus")
BLUEZ_WNK = WellKnownName("org.bluez")
OBJECT_MANAGER = InterfaceName("org.freedesktop.DBus.ObjectManager")
PROPERTIES = InterfaceName("org.freedesktop.DBus.Properties")


def is_unique_name(val: str) -> typing.TypeGuard[UniqueName]:
    return bool(UNIQUE_NAME_P.match(val))


def is_well_known_name(val: str) -> typing.TypeGuard[WellKnownName]:
    return bool(WELL_KNOWN_NAME_P.match(val))


def is_signal(msg: Message) -> typing.TypeGuard[Signal]:
    return msg.header.message_type == MessageType.signal


def remove_property_signatures(props: dict[PropertyName, tuple[Signature, typing.Any]]):
    return {key: value for key, (_, value) in props.items()}


class NameAwareMatchRule(MatchRule):
    wnk_sender: WellKnownName | None

    def __init__(
        self,
        *,
        type: str | MessageType = None,
        sender=None,
        interface=None,
        member=None,
        path=None,
        path_namespace=None,
        destination=None,
        eavesdrop=False,
    ):
        self.wnk_sender = None
        if sender is not None and is_well_known_name(sender):
            self.wnk_sender = sender
            sender = None
        super().__init__(
            type=type,
            sender=sender,
            interface=interface,
            member=member,
            path=path,
            path_namespace=path_namespace,
            destination=destination,
            eavesdrop=eavesdrop,
        )

    @typing.override
    def serialise(self) -> str:
        raise NotImplementedError("Never serialise a NameAwareMatchRule")

    def matches(self, msg: Message, name_owners: dict[WellKnownName, UniqueName]) -> bool:
        """Returns True if msg matches this rule"""
        if self.wnk_sender is not None:
            # This logic can never return True, because we still have to check the superclass method.
            # But it can shortcut return False.
            fields = typing.cast(dict[HeaderFields, typing.Any], msg.header.fields)
            sender = typing.cast(BusName, fields[HeaderFields.sender])
            # signals from the messagebus itself bear a well-known name instead of unique name
            if is_well_known_name(sender):
                if sender != self.wnk_sender:
                    return False
            elif is_unique_name(sender):
                if self.wnk_sender is BUS_WNK:
                    # sender is a unique name, but the bus sender will always be its well-known name.
                    return False
                if self.wnk_sender in name_owners:
                    if sender != name_owners.get(self.wnk_sender):
                        return False
                else:
                    logger.warning("Tried to match the unique name for %r, but we don't know it.", self.wnk_sender)
                    return False
        return super().matches(msg)


def message_outcome(msg: Message) -> outcome.Maybe[Message]:
    if msg.header.message_type == MessageType.error:
        return outcome.Error(DBusErrorResponse(msg))
    return outcome.Value(msg)


KnownInterfaceName = typing.NewType("KnownInterfaceName", InterfaceName)


def is_known_interface_name(val: str) -> typing.TypeGuard[KnownInterfaceName]:
    return val in {"org.bluez.Adapter1", "org.bluez.AgentManager1", "org.bluez.Device1"}


class DBusInterface(abc.ABC):
    __interface_name: typing.ClassVar[KnownInterfaceName]
    obj: DBusObject
    _properties: dict[PropertyName, typing.Any]

    def __init_subclass__(cls, *, interface_name: KnownInterfaceName, **kwargs: typing.Any):
        cls.__interface_name = interface_name
        super().__init_subclass__(**kwargs)

    def __init__(self, obj: DBusObject, properties: dict[str, typing.Any]):
        self.obj = weakref.proxy(obj)
        self.address = obj.address.with_interface(self.__interface_name)
        self._properties = properties

    async def _call_method(self, method, signature=None, body=()):
        return await self.obj.router.send_and_get_reply(new_method_call(self.address, method, signature, body))

    def _update_properties(self, properties: dict[PropertyName, typing.Any]):
        self._properties |= properties
        return self

    def _remove_properties(self, property_names: list[PropertyName]):
        for propname in property_names:
            if propname in self._properties:
                del self._properties[propname]

    async def _pset(self, name: PropertyName, signature: Signature, value: typing.Any):
        """Set the property *name* to *value* (with appropriate signature)"""
        address = self.address.with_interface(PROPERTIES)
        message = new_method_call(address, "Set", "ssv", (self.__interface_name, name, (signature, value)))
        await self.obj.router.send_and_get_reply(message)
        self._properties[name] = value

    def __contains__(self, name: PropertyName):
        return name in self._properties

    def __getitem__(self, name: PropertyName):
        return self._properties[name]


class DBusObject:
    router: BluezContext
    address: DBusAddress
    _interfaces: dict[KnownInterfaceName, DBusInterface]

    def __init__(self, router: BluezContext, address: DBusAddress):
        self.router = router
        self.address = address
        self._interfaces = {}

    @staticmethod
    def _interface_class(interface_name: KnownInterfaceName):
        match interface_name:
            case "org.bluez.Adapter1":
                return BluezAdapter
            case "org.bluez.AgentManager1":
                return BluezAgentManager
            case "org.bluez.Device1":
                return BluezDevice
        typing.assert_never()

    def _interface(self, interface_name: KnownInterfaceName):
        if interface_name not in self._interfaces:
            self._interfaces[interface_name] = self._interface_class(interface_name)(self, {})
        return self._interfaces[interface_name]

    def _remove_interface(self, interface_name: KnownInterfaceName):
        if interface_name in self._interfaces:
            del self._interfaces[interface_name]

    def __contains__(self, interface_name):
        return interface_name in self._interfaces

    def __getitem__(self, interface_name):
        return self._interfaces[interface_name]


class BluezAgentManager(DBusInterface, interface_name="org.bluez.AgentManager1"):
    async def RegisterAgent(self, agent: ObjectPath, capability: str):
        await self._call_method("RegisterAgent", "os", (agent, capability))

    async def UnregisterAgent(self, agent: ObjectPath):
        await self._call_method("UnregisterAgent", "o", (agent,))

    async def RequestDefaultAgent(self, agent: ObjectPath):
        await self._call_method("RequestDefaultAgent", "o", (agent,))


class BluezAdapter(DBusInterface, interface_name="org.bluez.Adapter1"):
    async def StartDiscovery(self):
        await self._call_method("StartDiscovery")

    async def SetDiscoveryFilter(self, properties: dict[str, typing.Any]):
        await self._call_method("SetDiscoveryFilter", "a{sv}", (properties,))

    async def StopDiscovery(self):
        await self._call_method("StopDiscovery")

    async def RemoveDevice(self, device: ObjectPath):
        await self._call_method("RemoveDevice", "o", (device,))

    async def GetDiscoveryFilters(self):
        return await self._call_method("GetDiscoveryFilters")

    async def SetPowered(self, value: bool):
        await self._pset("Powered", "b", value)

    async def SetPairable(self, value: bool):
        await self._pset("Pairable", "b", value)


class BluezDevice(DBusInterface, interface_name="org.bluez.Device1"):
    async def Disconnect(self):
        await self._call_method("Disconnect")

    async def Connect(self):
        await self._call_method("Connect")

    async def ConnectProfile(self, profile_uuid: str):
        await self._call_method("ConnectProfile", "s", (profile_uuid,))

    async def DisconnectProfile(self, profile_uuid: str):
        await self._call_method("DisconnectProfile", "s", (profile_uuid,))

    async def Pair(self):
        await self._call_method("Pair")

    async def CancelPairing(self):
        await self._call_method("CancelPairing")

    async def SetTrusted(self, value: bool):
        await self._pset("Trusted", "b", value)


class BluezError(Exception):
    __error_name: typing.ClassVar[str]

    def __init_subclass__(cls, *, error_name: str, **kwargs: typing.Any):
        cls.__error_name = f"org.bluez.Error.{error_name}"
        super().__init_subclass__(**kwargs)

    def to_error(self, respond_to: Message):
        return new_error(respond_to, self.__error_name)


class BluezRejected(BluezError, error_name="Rejected"):
    pass


class BluezCanceled(BluezError, error_name="Canceled"):
    pass


class BluezAgent:
    def __init__(self):
        self.logger = logger.getChild("BluezAgent")
        self.pincode = "123456"
        self.passkey = 654321
        self.confirm = True

    def Release(self) -> None:
        """
        This method gets called when the service daemon unregisters the agent.
        An agent can use it to do cleanup tasks. There is no need to unregister
        the agent, because when this method gets called it has already been
        unregistered.
        """
        self.logger.info("Release")

    def RequestPinCode(self, device: ObjectPath) -> str:
        """
        This method gets called when the service daemon needs to get the passkey
        for an authentication.

        The return value should be a string of 1-16 characters length. The
        string can be alphanumeric.
        """
        self.logger.info("RequestPinCode device: %r", device)
        return self.pincode

    def DisplayPinCode(self, device: ObjectPath, pincode: str) -> None:
        """
        This method gets called when the service daemon needs to display a
        pincode for an authentication.

        An empty reply should be returned. When the pincode needs no longer to
        be displayed, the Cancel method of the agent will be called.

        This is used during the pairing process of keyboards that don't support
        Bluetooth 2.1 Secure Simple Pairing, in contrast to DisplayPasskey which
        is used for those that do.

        This method will only ever be called once since older keyboards do not
        support typing notification.

        Note that the PIN will always be a 6-digit number, zero-padded to 6
        digits. This is for harmony with the later specification.
        """
        self.logger.info("DisplayPinCode device: %r, pincode: %r", device, pincode)

    def RequestPasskey(self, device: ObjectPath) -> int:
        """
        This method gets called when the service daemon needs to get the passkey
        for an authentication.

        The return value should be a numeric value between 0-999999.
        """
        self.logger.info("RequestPasskey device: %r", device)
        return self.passkey

    def DisplayPasskey(self, device: ObjectPath, passkey: int, entered: int) -> None:
        """
        This method gets called when the service daemon needs to display a
        passkey for an authentication.

        The entered parameter indicates the number of already typed keys on the
        remote side.

        An empty reply should be returned. When the passkey needs no longer to
        be displayed, the Cancel method of the agent will be called.

        During the pairing process this method might be called multiple times to
        update the entered value.

        Note that the passkey will always be a 6-digit number, so the display
        should be zero-padded at the start if the value contains less than 6
        digits.
        """
        self.logger.info("DisplayPasskey device: %r, passkey: %r, entered: %r", device, passkey, entered)

    def RequestConfirmation(self, device: ObjectPath, passkey: int) -> None:
        """
        This method gets called when the service daemon needs to confirm a
        passkey for an authentication.

        To confirm the value it should return an empty reply or an error in case
        the passkey is invalid.

        Note that the passkey will always be a 6-digit number, so the display
        should be zero-padded at the start if the value contains less than 6
        digits.
        """
        self.logger.info("RequestConfirmation device: %r, passkey: %r", device, passkey)
        if not self.confirm:
            raise BluezRejected()

    def RequestAuthorization(self, device: ObjectPath) -> None:
        """
        This method gets called to request the user to authorize an incoming
        pairing attempt which would in other circumstances trigger the
        just-works model, or when the user plugged in a device that implements
        cable pairing. In the latter case, the device would not be connected to
        the adapter via Bluetooth yet.
        """
        self.logger.info("RequestAuthorization device: %r", device)
        raise BluezCanceled()

    def AuthorizeService(self, device: ObjectPath, uuid: str) -> None:
        """
        This method gets called when the service daemon needs to authorize a
        connection/service request.
        """
        self.logger.info("AuthorizeService device: %r, uuid: %r", device, uuid)

    def Cancel(self) -> None:
        """
        This method gets called to indicate that the agent request failed before
        a reply was returned.
        """
        self.logger.info("Cancel")


class ExportedInterface:
    interface: typing.ClassVar[InterfaceName]
    introspection: typing.ClassVar[str | None] = None
    property_signatures: typing.ClassVar[dict[PropertyName, Signature] | None] = None

    @classmethod
    def _supports_introspection(cls):
        return cls.introspection is not None

    @classmethod
    def _supports_properties(cls):
        return cls.property_signatures is not None


class Agent1Interface(ExportedInterface):
    interface = InterfaceName("org.bluez.Agent1")
    # Technically this should just be the interface and not the node, but…
    introspection = textwrap.dedent(
        """\
        <!DOCTYPE node PUBLIC "-//freedesktop//DTD D-BUS Object Introspection 1.0//EN"
        "http://www.freedesktop.org/standards/dbus/1.0/introspect.dtd">
        <node>
            <interface name="org.bluez.Agent1">
                <method name="Release" />
                <method name="RequestPinCode">
                    <arg direction="in" type="o" />
                    <arg direction="out" type="s" />
                </method>
                <method name="DisplayPinCode">
                    <arg direction="in" type="o" />
                    <arg direction="in" type="s" />
                </method>
                <method name="RequestPasskey">
                    <arg direction="in" type="o" />
                    <arg direction="out" type="u" />
                </method>
                <method name="DisplayPasskey">
                    <arg direction="in" type="o" />
                    <arg direction="in" type="u" />
                    <arg direction="in" type="q" />
                </method>
                <method name="RequestConfirmation">
                    <arg direction="in" type="o" />
                    <arg direction="in" type="u" />
                </method>
                <method name="RequestAuthorization">
                    <arg direction="in" type="o" />
                </method>
                <method name="AuthorizeService">
                    <arg direction="in" type="o" />
                    <arg direction="in" type="s" />
                </method>
                <method name="Cancel" />
            </interface>
        </node>
        """
    )
    property_signatures = None

    def __init__(self, impl: BluezAgent):
        self.impl = impl

    def Release(self, msg: Message):
        self.impl.Release()
        return new_method_return(msg)

    def RequestPinCode(self, msg: Message):
        device = ObjectPath(msg.body[0])
        try:
            code = self.impl.RequestPinCode(device)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg, "s", (code,))

    def DisplayPinCode(self, msg: Message):
        device = ObjectPath(msg.body[0])
        code = typing.cast(str, msg.body[1])
        try:
            self.impl.DisplayPinCode(device, code)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg)

    def RequestPasskey(self, msg: Message):
        device = ObjectPath(msg.body[0])
        try:
            passkey = self.impl.RequestPasskey(device)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg, "u", (passkey,))

    def DisplayPasskey(self, msg: Message) -> None:
        device = ObjectPath(msg.body[0])
        passkey = typing.cast(int, msg.body[1])
        entered = typing.cast(int, msg.body[2])
        try:
            self.impl.DisplayPasskey(device, passkey, entered)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg)

    def RequestConfirmation(self, msg: Message):
        device = ObjectPath(msg.body[0])
        passkey = typing.cast(int, msg.body[1])
        try:
            self.impl.RequestConfirmation(device, passkey)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg)

    def RequestAuthorization(self, msg: Message):
        device = ObjectPath(msg.body[0])
        try:
            self.impl.RequestAuthorization(device)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg)

    def AuthorizeService(self, msg: Message):
        device = ObjectPath(msg.body[0])
        uuid = typing.cast(str, msg.body[1])
        try:
            self.impl.AuthorizeService(device, uuid)
        except BluezError as exc:
            return exc.to_error(msg)
        return new_method_return(msg)

    def Cancel(self, msg: Message):
        return new_method_return(msg)


OBJECT_MANAGER_GMO = (ObjectPath("/"), OBJECT_MANAGER, "GetManagedObjects")


class ExportedObjectManager:
    paths: dict[ObjectPath, list[ExportedInterface]]

    def __init__(self, router: BluezContext):
        self.router = router
        self.paths = collections.defaultdict(list)
        self.logger = logger.getChild("ExportedObjectManager")

    def _object_interfaces(self, interfaces: list[ExportedInterface]):
        result = {}
        for interface in interfaces:
            result[interface.interface] = {}
            if interface._supports_introspection():
                result["org.freedesktop.DBus.Introspectable"] = {}
            if interface._supports_properties():
                self.logger.warning("Interface %r supports properties but this isn't implemented yet", interface)
        return result

    async def export_interfaces(self, object_path: ObjectPath, *interfaces: ExportedInterface):
        self.paths[object_path].extend(interfaces)

        signal = new_signal(
            DBusAddress(bus_name=self.router.conn.unique_name, object_path="/", interface=OBJECT_MANAGER),
            "InterfacesAdded",
            "oa{sa{sv}}",
            (object_path, self._object_interfaces(interfaces)),
        )
        return await self.router.send_no_reply(signal)

    async def unexport_all(self):
        while self.paths:
            object_path, interfaces = self.paths.popitem()
            signal = new_signal(
                DBusAddress(bus_name=self.router.conn.unique_name, object_path="/", interface=OBJECT_MANAGER),
                "InterfacesRemoved",
                "oas",
                (object_path, [interface.interface for interface in interfaces]),
            )
            await self.router.send_no_reply(signal)

    async def respond(self, msg: Message):
        fields = typing.cast(dict[HeaderFields, str], msg.header.fields)
        object_path = ObjectPath(fields[HeaderFields.path])
        interface_name = InterfaceName(fields[HeaderFields.interface])
        method_name = fields[HeaderFields.member]

        if (object_path, interface_name, method_name) == OBJECT_MANAGER_GMO:
            result = {path: self._object_interfaces(interfaces) for path, interfaces in self.paths.items()}
            return await self.router.send_no_reply(new_method_return(msg, "a{oa{sa{sv}}}", (result,)))

        if interface_name == InterfaceName("org.freedesktop.DBus.Introspectable") and method_name == "Introspect":
            for interface in self.paths[object_path]:
                if interface._supports_introspection():
                    return await self.router.send_no_reply(new_method_return(msg, "s", (interface.introspection)))
            return await self.router.send_no_reply(new_error(msg, "org.freedesktop.DBus.Error.Failed"))

        if object_path in self.paths:
            for interface in self.paths[object_path]:
                if (
                    interface.interface == interface_name
                    and hasattr(interface, method_name)
                    and callable(method := getattr(interface, method_name))
                ):
                    response = method(msg)
                    return await self.router.send_no_reply(response)
        logger.warning("Unhandled method call %r", msg)
        return await self.router.send_no_reply(new_error(msg, "org.freedesktop.DBus.Error.Failed"))


class BluezContext(tricycle.BackgroundObject, daemon=True):
    conn: DBusConnection | None
    expected_replies: dict[int, trio.MemorySendChannel[outcome.Maybe[Message]]]
    name_owners: dict[WellKnownName, UniqueName]
    signal_watchers: list[tuple[NameAwareMatchRule, trio.MemorySendChannel[Signal]]]
    objects_by_path: dict[ObjectPath, DBusObject]
    waiting_predicates: list[tuple[collections.abc.Callable, trio.Event]]

    def __init__(self):
        self.conn = None
        self.expected_replies = {}
        self.name_owners = {}
        self.signal_watchers = []
        self.objects_by_path = {}
        self.waiting_predicates = []
        self.exported_object_manager = ExportedObjectManager(self)

    async def _receiver(self, *, task_status=trio.TASK_STATUS_IGNORED):
        if self.conn is None:
            raise RouterClosed("Not connected to D-Bus")
        recv_logger = logger.getChild("allmessages")
        task_status.started()
        try:
            async for msg in self.conn:
                recv_logger.debug("BlueGroove received message %r", msg)
                if msg.header.message_type in (MessageType.method_return, MessageType.error):
                    reply_to = msg.header.fields.get(HeaderFields.reply_serial, -1)
                    if reply_to in self.expected_replies:
                        reply_channel = self.expected_replies.pop(reply_to)
                        reply_channel.send_nowait(message_outcome(msg))
                    else:
                        recv_logger.warning("Got unexpected message of type %r with reply_serial %d", msg.header.message_type, reply_to)
                if is_signal(msg):
                    for rule, channel in self.signal_watchers:
                        if rule.matches(msg, name_owners=self.name_owners):
                            await channel.send(msg)
                if msg.header.message_type == MessageType.method_call:
                    await self.exported_object_manager.respond(msg)
                self.check_predicates()
        except Exception:
            logger.exception("something unexpected happened")
        finally:
            logger.debug("D-Bus connection closed")
            for reply_channel in self.expected_replies.values():
                reply_channel.send_nowait(outcome.Error(RouterClosed("D-Bus connection closed before reply arrived")))
            self.expected_replies = {}

    def check_predicates(self):
        for predicate, event in self.waiting_predicates:
            if predicate(self.objects_by_path):
                event.set()
        self.waiting_predicates = [item for item in self.waiting_predicates if not item[1].is_set()]

    async def _name_watcher(self, recv: trio.MemoryReceiveChannel[Signal], *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        with recv:
            while True:
                signal = await recv.receive()
                wnk = signal.body[0]
                assert is_well_known_name(wnk)
                new_owner = signal.body[2] or None
                if new_owner is None:
                    logger.debug("Defunct name %r", wnk)
                    if wnk in self.name_owners:
                        del self.name_owners[wnk]
                else:
                    assert is_unique_name(new_owner)
                    logger.debug("Name %r now owned by %r", wnk, new_owner)
                    self.name_owners[wnk] = new_owner

    async def _interface_watcher(self, recv: trio.MemoryReceiveChannel[Signal], *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        with recv:
            while True:
                signal = await recv.receive()
                fields = typing.cast(dict[HeaderFields, any], signal.header.fields)
                signal_type = fields[HeaderFields.member]
                match signal_type:
                    case "InterfacesRemoved":
                        object_path = ObjectPath(signal.body[0])
                        if object_path not in self.objects_by_path:
                            continue
                        obj = self.objects_by_path[object_path]
                        for iface_name in signal.body[1]:
                            iface_name = InterfaceName(iface_name)
                            if is_known_interface_name(iface_name):
                                obj._remove_interface(iface_name)
                        if len(obj._interfaces) == 0:
                            logging.debug("Object %r went away", object_path)
                            del self.objects_by_path[object_path]
                    case "InterfacesAdded":
                        self._update_object_interfaces(
                            self._object_at_path(bus_name="org.bluez", object_path=ObjectPath(signal.body[0])), signal.body[1]
                        )
                    case _:
                        raise Exception("Unexpected signal type %r" % signal_type)

    async def _property_watcher(self, recv: trio.MemoryReceiveChannel[Signal], *, task_status=trio.TASK_STATUS_IGNORED):
        task_status.started()
        with recv:
            while True:
                signal = await recv.receive()
                fields = typing.cast(dict[HeaderFields, any], signal.header.fields)
                object_path = ObjectPath(fields[HeaderFields.path])
                if object_path not in self.objects_by_path:
                    continue
                obj = self.objects_by_path[object_path]
                iface_name = signal.body[0]
                if iface_name not in obj._interfaces:
                    continue
                interface = obj._interfaces[iface_name]
                interface._update_properties(remove_property_signatures(signal.body[1]))
                if signal.body[2]:
                    interface._remove_properties(signal.body[2])

    async def send_no_reply(self, message: Message):
        if self.conn is None:
            raise RouterClosed("Not connected to D-Bus")
        message.header.flags |= MessageFlag.no_reply_expected
        await self.conn.send(message)

    async def send_and_get_reply(self, message: Message):
        if self.conn is None:
            raise RouterClosed("Not connected to D-Bus")
        check_replyable(message)
        serial = next(self.conn.outgoing_serial)
        send_, recv_ = trio.open_memory_channel[outcome.Maybe[Message]](1)
        self.expected_replies[serial] = send_
        await self.conn.send(message, serial=serial)
        with recv_:
            maybe = await recv_.receive()
            return maybe.unwrap()

    async def track_well_known_name(self, wnk: WellKnownName):
        if wnk in self.name_owners:
            # already tracking it
            return
        rule = MatchRule(type="signal", sender="org.freedesktop.DBus", interface="org.freedesktop.DBus", member="NameOwnerChanged")
        rule.add_arg_condition(0, wnk)
        await self.send_no_reply(message_bus.AddMatch(rule))
        try:
            r = await self.send_and_get_reply(message_bus.GetNameOwner(wnk))
            owner = UniqueName(r.body[0])
            self.name_owners[wnk] = owner
        except DBusErrorResponse as exc:
            if exc.name != "org.freedesktop.DBus.Error.NameHasNoOwner":
                raise

    def _object_at_path(self, bus_name: BusName, object_path: ObjectPath):
        if object_path not in self.objects_by_path:
            self.objects_by_path[object_path] = DBusObject(router=self, address=DBusAddress(object_path=object_path, bus_name=bus_name))
        return self.objects_by_path[object_path]

    def _update_object_interfaces(
        self, obj: DBusObject, interface_props: dict[InterfaceName, dict[PropertyName, tuple[Signature, typing.Any]]]
    ):
        for ifacename, props in interface_props.items():
            if not is_known_interface_name(ifacename):
                continue
            obj._interface(ifacename)._update_properties(remove_property_signatures(props))

    async def get_managed_objects(self, address: DBusAddress):
        msg = new_method_call(address.with_interface(OBJECT_MANAGER), "GetManagedObjects")
        response = await self.send_and_get_reply(msg)
        for object_path, ifacedict in response.body[0].items():
            obj = self._object_at_path(address.bus_name, ObjectPath(object_path))
            self._update_object_interfaces(obj, ifacedict)

    def objects_below_path(self, some_path: ObjectPath):
        return tuple(obj for obj_path, obj in self.objects_by_path.items() if obj_path.startswith(some_path) and obj_path != some_path)

    @property
    def agent_manager(self):
        for obj in self.objects_by_path.values():
            if "org.bluez.Adapter1" in obj:
                return obj["org.bluez.AgentManager1"]

    @property
    def adapter(self):
        for obj in self.objects_by_path.values():
            if "org.bluez.Adapter1" in obj:
                return obj["org.bluez.Adapter1"]

    @property
    def devices(self):
        return {path: obj["org.bluez.Device1"] for path, obj in self.objects_by_path.items() if "org.bluez.Device1" in obj}

    async def install_agent(self, object_path: ObjectPath):
        agent = BluezAgent()
        wrapper = Agent1Interface(agent)
        await self.exported_object_manager.export_interfaces(object_path, wrapper)
        await self.agent_manager.RegisterAgent(object_path, "DisplayYesNo")
        return agent

    async def wait_for_adapter(self):
        def predicate(objects_by_path):
            return any("org.bluez.Adapter1" in obj for obj in objects_by_path.values())

        event = trio.Event()
        self.waiting_predicates.append((predicate, event))
        self.check_predicates()  # it may already be there…
        await event.wait()

    async def ensure_adapter_powered_on(self):
        await self.wait_for_adapter()
        if not self.adapter["Powered"]:
            await self.adapter.SetPowered(True)

    @contextlib.asynccontextmanager
    async def __wrap__(self):
        self.expected_replies = {}
        self.name_owners = {}
        self.signal_watchers = []
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(super().__wrap__())
            self.conn = await stack.enter_async_context(await open_dbus_connection(bus="SYSTEM"))
            await self.nursery.start(self._receiver)
            send_, recv_ = trio.open_memory_channel[Signal](3)
            await self.nursery.start(self._name_watcher, recv_)
            self.signal_watchers.append(
                (
                    NameAwareMatchRule(sender="org.freedesktop.DBus", interface="org.freedesktop.DBus", member="NameOwnerChanged"),
                    send_,
                )
            )
            await self.track_well_known_name(BLUEZ_WNK)

            send_, recv_ = trio.open_memory_channel[Signal](3)
            await self.nursery.start(self._interface_watcher, recv_)
            self.signal_watchers.append(
                (
                    NameAwareMatchRule(
                        sender=BLUEZ_WNK,
                        interface=OBJECT_MANAGER,
                        member="InterfacesAdded",
                    ),
                    send_.clone(),
                )
            )
            self.signal_watchers.append(
                (
                    NameAwareMatchRule(
                        sender=BLUEZ_WNK,
                        interface=OBJECT_MANAGER,
                        member="InterfacesRemoved",
                    ),
                    send_.clone(),
                )
            )

            send_, recv_ = trio.open_memory_channel[Signal](3)
            await self.nursery.start(self._property_watcher, recv_)
            self.signal_watchers.append(
                (
                    NameAwareMatchRule(
                        sender=BLUEZ_WNK,
                        interface=PROPERTIES,
                        member="PropertiesChanged",
                    ),
                    send_,
                )
            )

            await self.send_no_reply(
                message_bus.AddMatch(
                    MatchRule(
                        type="signal",
                        sender=BLUEZ_WNK,
                        interface=OBJECT_MANAGER,
                        member="InterfacesAdded",
                    )
                )
            )
            await self.send_no_reply(
                message_bus.AddMatch(
                    MatchRule(
                        type="signal",
                        sender=BLUEZ_WNK,
                        interface=OBJECT_MANAGER,
                        member="InterfacesRemoved",
                    )
                )
            )
            await self.send_no_reply(
                message_bus.AddMatch(
                    MatchRule(
                        type="signal",
                        sender=BLUEZ_WNK,
                        interface=PROPERTIES,
                        member="PropertiesChanged",
                    )
                )
            )
            # kick things off by requesting the objects
            await self.get_managed_objects(DBusAddress(object_path="/", bus_name=BLUEZ_WNK))
            yield
            await self.exported_object_manager.unexport_all()
            self.conn = None


if __name__ == "__main__":
    # importing readline makes arrow keys work properly.
    import readline  # noqa: F401

    import trio._repl

    logging.basicConfig(level=logging.DEBUG)
    logger.getChild("allmessages").setLevel(logging.INFO)

    async def main():
        async with BluezContext() as bluezcontext:
            await bluezcontext.wait_for_adapter()
            logger.debug("Started")
            console = trio._repl.TrioInteractiveConsole(
                {
                    "trio": trio,
                    "bluezcontext": bluezcontext,
                    "nursery": bluezcontext.nursery,
                    "BluezAgentManager": BluezAgentManager,
                    "BluezAdapter": BluezAdapter,
                    "BluezDevice": BluezDevice,
                    "BluezAgent": BluezAgent,
                    "Agent1Interface": Agent1Interface,
                }
            )
            await trio._repl.run_repl(console)

    trio.run(main)
