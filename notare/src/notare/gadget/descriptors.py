# SPDX-License-Identifier: GPL-3.0-or-later

from ._usb import lib as usblib, ffi as usbffi


def descriptors():
    val = usbffi.new("struct descriptors *")
    val.header.magic = usblib.FUNCTIONFS_DESCRIPTORS_MAGIC_V2
    val.header.flags = usblib.FUNCTIONFS_HAS_FS_DESC | usblib.FUNCTIONFS_HAS_HS_DESC
    val.header.length = usbffi.sizeof("struct descriptors")

    val.fs_count = 4
    val.hs_count = 4

    ed_sizeof = usbffi.sizeof("struct usb_endpoint_descriptor_no_audio")

    for speed_descs, high_speed in ((val.fs_descs, False), (val.hs_descs, True)):
        speed_descs.intf.bLength = usbffi.sizeof("struct usb_interface_descriptor")
        speed_descs.intf.bDescriptorType = usblib.USB_DT_INTERFACE
        speed_descs.intf.bNumEndpoints = 3
        speed_descs.intf.bInterfaceClass = usblib.USB_CLASS_VENDOR_SPEC
        speed_descs.intf.iInterface = 1

        speed_descs.frames.bLength = ed_sizeof
        speed_descs.frames.bDescriptorType = usblib.USB_DT_ENDPOINT
        speed_descs.frames.bEndpointAddress = 1 | usblib.USB_DIR_OUT
        speed_descs.frames.bmAttributes = usblib.USB_ENDPOINT_XFER_BULK
        if high_speed:
            speed_descs.frames.wMaxPacketSize = 512
            speed_descs.frames.bInterval = 1  # NAK at most every 1 uframe

        speed_descs.host_events.bLength = ed_sizeof
        speed_descs.host_events.bDescriptorType = usblib.USB_DT_ENDPOINT
        speed_descs.host_events.bEndpointAddress = 2 | usblib.USB_DIR_OUT
        speed_descs.host_events.bmAttributes = usblib.USB_ENDPOINT_XFER_INT
        if high_speed:
            speed_descs.host_events.wMaxPacketSize = 512

        speed_descs.device_events.bLength = ed_sizeof
        speed_descs.device_events.bDescriptorType = usblib.USB_DT_ENDPOINT
        speed_descs.device_events.bEndpointAddress = 3 | usblib.USB_DIR_IN
        speed_descs.device_events.bmAttributes = usblib.USB_ENDPOINT_XFER_INT
        if high_speed:
            speed_descs.host_events.wMaxPacketSize = 512

    return usbffi.buffer(val)


def strings():
    val = usbffi.new("struct strings *")
    val.header.magic = usblib.FUNCTIONFS_STRINGS_MAGIC
    val.header.length = usbffi.sizeof("struct strings")
    val.header.str_count = 1
    val.header.lang_count = 1
    val.lang0.code = 0x0409
    # exactly 15 bytes are reserved for this, and it's a null-terminated string. be careful.
    # if you want to resize it, look at the 'strings' struct defined in _usb_build.py
    val.lang0.str1 = b"Tabula display"

    return usbffi.buffer(val)
