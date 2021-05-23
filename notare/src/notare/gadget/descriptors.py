# SPDX-License-Identifier: GPL-3.0-or-later

from ._usb import lib as usblib, ffi as usbffi


def descriptors():
    val = usbffi.new("struct descriptors *")
    val.header.magic = usblib.FUNCTIONFS_DESCRIPTORS_MAGIC_V2
    val.header.flags = usblib.FUNCTIONFS_HAS_FS_DESC | usblib.FUNCTIONFS_HAS_HS_DESC
    val.header.length = usbffi.sizeof("struct descriptors")
    val.fs_count = 3
    val.fs_descs.intf.bLength = usbffi.sizeof("struct usb_interface_descriptor")
    val.fs_descs.intf.bDescriptorType = usblib.USB_DT_INTERFACE
    val.fs_descs.intf.bNumEndpoints = 2
    val.fs_descs.intf.bInterfaceClass = usblib.USB_CLASS_VENDOR_SPEC
    val.fs_descs.intf.iInterface = 1
    val.fs_descs.frames.bLength = usbffi.sizeof(
        "struct usb_endpoint_descriptor_no_audio"
    )
    val.fs_descs.frames.bDescriptorType = usblib.USB_DT_ENDPOINT
    val.fs_descs.frames.bEndpointAddress = 1 | usblib.USB_DIR_OUT
    val.fs_descs.frames.bmAttributes = usblib.USB_ENDPOINT_XFER_BULK
    val.fs_descs.events.bLength = usbffi.sizeof(
        "struct usb_endpoint_descriptor_no_audio"
    )
    val.fs_descs.events.bDescriptorType = usblib.USB_DT_ENDPOINT
    val.fs_descs.events.bEndpointAddress = 2 | usblib.USB_DIR_IN
    val.fs_descs.events.bmAttributes = usblib.USB_ENDPOINT_XFER_INT
    val.hs_count = 3
    val.hs_descs.intf.bLength = usbffi.sizeof("struct usb_interface_descriptor")
    val.hs_descs.intf.bDescriptorType = usblib.USB_DT_INTERFACE
    val.hs_descs.intf.bNumEndpoints = 2
    val.hs_descs.intf.bInterfaceClass = usblib.USB_CLASS_VENDOR_SPEC
    val.hs_descs.intf.iInterface = 1
    val.hs_descs.frames.bLength = usbffi.sizeof(
        "struct usb_endpoint_descriptor_no_audio"
    )
    val.hs_descs.frames.bDescriptorType = usblib.USB_DT_ENDPOINT
    val.hs_descs.frames.bEndpointAddress = 1 | usblib.USB_DIR_OUT
    val.hs_descs.frames.bmAttributes = usblib.USB_ENDPOINT_XFER_BULK
    val.hs_descs.frames.wMaxPacketSize = 512
    val.hs_descs.frames.bInterval = 1  # NAK every 1 uframe
    val.hs_descs.events.bLength = usbffi.sizeof(
        "struct usb_endpoint_descriptor_no_audio"
    )
    val.hs_descs.events.bDescriptorType = usblib.USB_DT_ENDPOINT
    val.hs_descs.events.bEndpointAddress = 2 | usblib.USB_DIR_IN
    val.hs_descs.events.bmAttributes = usblib.USB_ENDPOINT_XFER_INT
    val.hs_descs.events.wMaxPacketSize = 512

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
