# SPDX-License-Identifier: GPL-3.0-or-later
import os.path

from cffi import FFI

ffibuilder = FFI()

ffibuilder.cdef('''
/* asm-generic/int-ll64.h */

typedef signed char __s8;
typedef unsigned char __u8;

typedef signed short __s16;
typedef unsigned short __u16;

typedef signed int __s32;
typedef unsigned int __u32;

typedef signed long long __s64;
typedef unsigned long long __u64;

typedef __u16  __le16;
typedef __u16  __be16;
typedef __u32  __le32;
typedef __u32  __be32;
typedef __u64  __le64;
typedef __u64  __be64;

typedef __u16  __sum16;
typedef __u32  __wsum;
''')

ffibuilder.cdef('''
/* linux/usb/ch9.h */

/*
 * USB directions
 *
 * This bit flag is used in endpoint descriptors' bEndpointAddress field.
 * It's also one of three fields in control requests bRequestType.
 */
#define USB_DIR_OUT			...		/* to device */
#define USB_DIR_IN			...		/* to host */

/*
 * USB types, the second of three bRequestType fields
 */
#define USB_TYPE_MASK			...
#define USB_TYPE_STANDARD		...
#define USB_TYPE_CLASS			...
#define USB_TYPE_VENDOR			...
#define USB_TYPE_RESERVED		...

/*
 * USB recipients, the third of three bRequestType fields
 */
#define USB_RECIP_MASK			...
#define USB_RECIP_DEVICE		...
#define USB_RECIP_INTERFACE		...
#define USB_RECIP_ENDPOINT		...
#define USB_RECIP_OTHER			...
/* From Wireless USB 1.0 */
#define USB_RECIP_PORT			...
#define USB_RECIP_RPIPE		...

/*
 * Standard requests, for the bRequest field of a SETUP packet.
 *
 * These are qualified by the bRequestType field, so that for example
 * TYPE_CLASS or TYPE_VENDOR specific feature flags could be retrieved
 * by a GET_STATUS request.
 */
#define USB_REQ_GET_STATUS		...
#define USB_REQ_CLEAR_FEATURE		...
#define USB_REQ_SET_FEATURE		...
#define USB_REQ_SET_ADDRESS		...
#define USB_REQ_GET_DESCRIPTOR		...
#define USB_REQ_SET_DESCRIPTOR		...
#define USB_REQ_GET_CONFIGURATION	...
#define USB_REQ_SET_CONFIGURATION	...
#define USB_REQ_GET_INTERFACE		...
#define USB_REQ_SET_INTERFACE		...
#define USB_REQ_SYNCH_FRAME		...
#define USB_REQ_SET_SEL			...
#define USB_REQ_SET_ISOCH_DELAY		...

#define USB_REQ_SET_ENCRYPTION		0x0D	/* Wireless USB */
#define USB_REQ_GET_ENCRYPTION		0x0E
#define USB_REQ_RPIPE_ABORT		0x0E
#define USB_REQ_SET_HANDSHAKE		0x0F
#define USB_REQ_RPIPE_RESET		0x0F
#define USB_REQ_GET_HANDSHAKE		0x10
#define USB_REQ_SET_CONNECTION		0x11
#define USB_REQ_SET_SECURITY_DATA	0x12
#define USB_REQ_GET_SECURITY_DATA	0x13
#define USB_REQ_SET_WUSB_DATA		0x14
#define USB_REQ_LOOPBACK_DATA_WRITE	0x15
#define USB_REQ_LOOPBACK_DATA_READ	0x16
#define USB_REQ_SET_INTERFACE_DS	0x17

/* The Link Power Management (LPM) ECN defines USB_REQ_TEST_AND_SET command,
 * used by hubs to put ports into a new L1 suspend state, except that it
 * forgot to define its number ...
 */

/*
 * USB feature flags are written using USB_REQ_{CLEAR,SET}_FEATURE, and
 * are read as a bit array returned by USB_REQ_GET_STATUS.  (So there
 * are at most sixteen features of each type.)  Hubs may also support a
 * new USB_REQ_TEST_AND_SET_FEATURE to put ports into L1 suspend.
 */
#define USB_DEVICE_SELF_POWERED		0	/* (read only) */
#define USB_DEVICE_REMOTE_WAKEUP	1	/* dev may initiate wakeup */
#define USB_DEVICE_TEST_MODE		2	/* (wired high speed only) */
#define USB_DEVICE_BATTERY		2	/* (wireless) */
#define USB_DEVICE_B_HNP_ENABLE		3	/* (otg) dev may initiate HNP */
#define USB_DEVICE_WUSB_DEVICE		3	/* (wireless)*/
#define USB_DEVICE_A_HNP_SUPPORT	4	/* (otg) RH port supports HNP */
#define USB_DEVICE_A_ALT_HNP_SUPPORT	5	/* (otg) other RH port does */
#define USB_DEVICE_DEBUG_MODE		6	/* (special devices only) */

/*
 * Test Mode Selectors
 * See USB 2.0 spec Table 9-7
 */
#define	TEST_J		1
#define	TEST_K		2
#define	TEST_SE0_NAK	3
#define	TEST_PACKET	4
#define	TEST_FORCE_EN	5
#define	TEST_OTG_SRP_REQD	6
#define	TEST_OTG_HNP_REQD	7

/*
 * New Feature Selectors as added by USB 3.0
 * See USB 3.0 spec Table 9-7
 */
#define USB_DEVICE_U1_ENABLE	48	/* dev may initiate U1 transition */
#define USB_DEVICE_U2_ENABLE	49	/* dev may initiate U2 transition */
#define USB_DEVICE_LTM_ENABLE	50	/* dev may send LTM */
#define USB_INTRF_FUNC_SUSPEND	0	/* function suspend */

#define USB_INTR_FUNC_SUSPEND_OPT_MASK	0xFF00
/*
 * Suspend Options, Table 9-8 USB 3.0 spec
 */
#define USB_INTRF_FUNC_SUSPEND_LP	...
#define USB_INTRF_FUNC_SUSPEND_RW	...

/*
 * Interface status, Figure 9-5 USB 3.0 spec
 */
#define USB_INTRF_STAT_FUNC_RW_CAP     1
#define USB_INTRF_STAT_FUNC_RW         2

#define USB_ENDPOINT_HALT		0	/* IN/OUT will STALL */

/* Bit array elements as returned by the USB_REQ_GET_STATUS request. */
#define USB_DEV_STAT_U1_ENABLED		2	/* transition into U1 state */
#define USB_DEV_STAT_U2_ENABLED		3	/* transition into U2 state */
#define USB_DEV_STAT_LTM_ENABLED	4	/* Latency tolerance messages */

/**
 * struct usb_ctrlrequest - SETUP data for a USB device control request
 * @bRequestType: matches the USB bmRequestType field
 * @bRequest: matches the USB bRequest field
 * @wValue: matches the USB wValue field (le16 byte order)
 * @wIndex: matches the USB wIndex field (le16 byte order)
 * @wLength: matches the USB wLength field (le16 byte order)
 *
 * This structure is used to send control requests to a USB device.  It matches
 * the different fields of the USB 2.0 Spec section 9.3, table 9-2.  See the
 * USB spec for a fuller description of the different fields, and what they are
 * used for.
 *
 * Note that the driver for any interface can issue control requests.
 * For most devices, interfaces don't coordinate with each other, so
 * such requests may be made at any time.
 */
struct usb_ctrlrequest {
	__u8 bRequestType;
	__u8 bRequest;
	__le16 wValue;
	__le16 wIndex;
	__le16 wLength;
};

/*-------------------------------------------------------------------------*/

/*
 * STANDARD DESCRIPTORS ... as returned by GET_DESCRIPTOR, or
 * (rarely) accepted by SET_DESCRIPTOR.
 *
 * Note that all multi-byte values here are encoded in little endian
 * byte order "on the wire".  Within the kernel and when exposed
 * through the Linux-USB APIs, they are not converted to cpu byte
 * order; it is the responsibility of the client code to do this.
 * The single exception is when device and configuration descriptors (but
 * not other descriptors) are read from usbfs (i.e. /proc/bus/usb/BBB/DDD);
 * in this case the fields are converted to host endianness by the kernel.
 */

/*
 * Descriptor types ... USB 2.0 spec table 9.5
 */
#define USB_DT_DEVICE			0x01
#define USB_DT_CONFIG			0x02
#define USB_DT_STRING			0x03
#define USB_DT_INTERFACE		0x04
#define USB_DT_ENDPOINT			0x05
#define USB_DT_DEVICE_QUALIFIER		0x06
#define USB_DT_OTHER_SPEED_CONFIG	0x07
#define USB_DT_INTERFACE_POWER		0x08
/* these are from a minor usb 2.0 revision (ECN) */
#define USB_DT_OTG			0x09
#define USB_DT_DEBUG			0x0a
#define USB_DT_INTERFACE_ASSOCIATION	0x0b
/* these are from the Wireless USB spec */
#define USB_DT_SECURITY			0x0c
#define USB_DT_KEY			0x0d
#define USB_DT_ENCRYPTION_TYPE		0x0e
#define USB_DT_BOS			0x0f
#define USB_DT_DEVICE_CAPABILITY	0x10
#define USB_DT_WIRELESS_ENDPOINT_COMP	0x11
#define USB_DT_WIRE_ADAPTER		0x21
#define USB_DT_RPIPE			0x22
#define USB_DT_CS_RADIO_CONTROL		0x23
/* From the T10 UAS specification */
#define USB_DT_PIPE_USAGE		0x24
/* From the USB 3.0 spec */
#define	USB_DT_SS_ENDPOINT_COMP		0x30

/* Conventional codes for class-specific descriptors.  The convention is
 * defined in the USB "Common Class" Spec (3.11).  Individual class specs
 * are authoritative for their usage, not the "common class" writeup.
 */
#define USB_DT_CS_DEVICE		...
#define USB_DT_CS_CONFIG		...
#define USB_DT_CS_STRING		...
#define USB_DT_CS_INTERFACE		...
#define USB_DT_CS_ENDPOINT		...

/* All standard descriptors have these 2 fields at the beginning */
struct usb_descriptor_header {
	__u8  bLength;
	__u8  bDescriptorType;
};


/*-------------------------------------------------------------------------*/

/* USB_DT_DEVICE: Device descriptor */
struct usb_device_descriptor {
	__u8  bLength;
	__u8  bDescriptorType;

	__le16 bcdUSB;
	__u8  bDeviceClass;
	__u8  bDeviceSubClass;
	__u8  bDeviceProtocol;
	__u8  bMaxPacketSize0;
	__le16 idVendor;
	__le16 idProduct;
	__le16 bcdDevice;
	__u8  iManufacturer;
	__u8  iProduct;
	__u8  iSerialNumber;
	__u8  bNumConfigurations;
};

#define USB_DT_DEVICE_SIZE		18


/*
 * Device and/or Interface Class codes
 * as found in bDeviceClass or bInterfaceClass
 * and defined by www.usb.org documents
 */
#define USB_CLASS_PER_INTERFACE		0	/* for DeviceClass */
#define USB_CLASS_AUDIO			1
#define USB_CLASS_COMM			2
#define USB_CLASS_HID			3
#define USB_CLASS_PHYSICAL		5
#define USB_CLASS_STILL_IMAGE		6
#define USB_CLASS_PRINTER		7
#define USB_CLASS_MASS_STORAGE		8
#define USB_CLASS_HUB			9
#define USB_CLASS_CDC_DATA		0x0a
#define USB_CLASS_CSCID			0x0b	/* chip+ smart card */
#define USB_CLASS_CONTENT_SEC		0x0d	/* content security */
#define USB_CLASS_VIDEO			0x0e
#define USB_CLASS_WIRELESS_CONTROLLER	0xe0
#define USB_CLASS_MISC			0xef
#define USB_CLASS_APP_SPEC		0xfe
#define USB_CLASS_VENDOR_SPEC		0xff

#define USB_SUBCLASS_VENDOR_SPEC	0xff

/*-------------------------------------------------------------------------*/

/* USB_DT_CONFIG: Configuration descriptor information.
 *
 * USB_DT_OTHER_SPEED_CONFIG is the same descriptor, except that the
 * descriptor type is different.  Highspeed-capable devices can look
 * different depending on what speed they're currently running.  Only
 * devices with a USB_DT_DEVICE_QUALIFIER have any OTHER_SPEED_CONFIG
 * descriptors.
 */
struct usb_config_descriptor {
	__u8  bLength;
	__u8  bDescriptorType;

	__le16 wTotalLength;
	__u8  bNumInterfaces;
	__u8  bConfigurationValue;
	__u8  iConfiguration;
	__u8  bmAttributes;
	__u8  bMaxPower;
};

#define USB_DT_CONFIG_SIZE		9

/* from config descriptor bmAttributes */
#define USB_CONFIG_ATT_ONE		...	/* must be set */
#define USB_CONFIG_ATT_SELFPOWER	...	/* self powered */
#define USB_CONFIG_ATT_WAKEUP		...	/* can wakeup */
#define USB_CONFIG_ATT_BATTERY		...	/* battery powered */

/*-------------------------------------------------------------------------*/

/* USB_DT_STRING: String descriptor */
struct usb_string_descriptor {
	__u8  bLength;
	__u8  bDescriptorType;

	__le16 wData[1];		/* UTF-16LE encoded */
};

/* note that "string" zero is special, it holds language codes that
 * the device supports, not Unicode characters.
 */

/*-------------------------------------------------------------------------*/

/* USB_DT_INTERFACE: Interface descriptor */
struct usb_interface_descriptor {
	__u8  bLength;
	__u8  bDescriptorType;

	__u8  bInterfaceNumber;
	__u8  bAlternateSetting;
	__u8  bNumEndpoints;
	__u8  bInterfaceClass;
	__u8  bInterfaceSubClass;
	__u8  bInterfaceProtocol;
	__u8  iInterface;
};

#define USB_DT_INTERFACE_SIZE		9

/*-------------------------------------------------------------------------*/

/* USB_DT_ENDPOINT: Endpoint descriptor */
struct usb_endpoint_descriptor {
	__u8  bLength;
	__u8  bDescriptorType;

	__u8  bEndpointAddress;
	__u8  bmAttributes;
	__le16 wMaxPacketSize;
	__u8  bInterval;

	/* NOTE:  these two are _only_ in audio endpoints. */
	/* use USB_DT_ENDPOINT*_SIZE in bLength, not sizeof. */
	__u8  bRefresh;
	__u8  bSynchAddress;
};

#define USB_DT_ENDPOINT_SIZE		7
#define USB_DT_ENDPOINT_AUDIO_SIZE	9	/* Audio extension */


/*
 * Endpoints
 */
#define USB_ENDPOINT_NUMBER_MASK	0x0f	/* in bEndpointAddress */
#define USB_ENDPOINT_DIR_MASK		0x80

#define USB_ENDPOINT_XFERTYPE_MASK	0x03	/* in bmAttributes */
#define USB_ENDPOINT_XFER_CONTROL	0
#define USB_ENDPOINT_XFER_ISOC		1
#define USB_ENDPOINT_XFER_BULK		2
#define USB_ENDPOINT_XFER_INT		3
#define USB_ENDPOINT_MAX_ADJUSTABLE	0x80

/* The USB 3.0 spec redefines bits 5:4 of bmAttributes as interrupt ep type. */
#define USB_ENDPOINT_INTRTYPE		0x30
#define USB_ENDPOINT_INTR_PERIODIC	...
#define USB_ENDPOINT_INTR_NOTIFICATION	...

#define USB_ENDPOINT_SYNCTYPE		0x0c
#define USB_ENDPOINT_SYNC_NONE		...
#define USB_ENDPOINT_SYNC_ASYNC		...
#define USB_ENDPOINT_SYNC_ADAPTIVE	...
#define USB_ENDPOINT_SYNC_SYNC		...

#define USB_ENDPOINT_USAGE_MASK		0x30
#define USB_ENDPOINT_USAGE_DATA		0x00
#define USB_ENDPOINT_USAGE_FEEDBACK	0x10
#define USB_ENDPOINT_USAGE_IMPLICIT_FB	0x20	/* Implicit feedback Data endpoint */

''', packed=True)

ffibuilder.cdef('''
/* linux/usb/functionfs.h */

enum {
	FUNCTIONFS_DESCRIPTORS_MAGIC = 1,
	FUNCTIONFS_STRINGS_MAGIC = 2,
	FUNCTIONFS_DESCRIPTORS_MAGIC_V2 = 3,
};

enum functionfs_flags {
	FUNCTIONFS_HAS_FS_DESC = 1,
	FUNCTIONFS_HAS_HS_DESC = 2,
	FUNCTIONFS_HAS_SS_DESC = 4,
	FUNCTIONFS_HAS_MS_OS_DESC = 8,
	FUNCTIONFS_VIRTUAL_ADDR = 16,
	FUNCTIONFS_EVENTFD = 32,
};

/* Descriptor of an non-audio endpoint */
struct usb_endpoint_descriptor_no_audio {
	__u8  bLength;
	__u8  bDescriptorType;

	__u8  bEndpointAddress;
	__u8  bmAttributes;
	__le16 wMaxPacketSize;
	__u8  bInterval;
};

struct usb_functionfs_descs_head_v2 {
	__le32 magic;
	__le32 length;
	__le32 flags;
} ;

/* MS OS Descriptor header */
struct usb_os_desc_header {
	__u8	interface;
	__le32	dwLength;
	__le16	bcdVersion;
	__le16	wIndex;
	union {
		struct {
			__u8	bCount;
			__u8	Reserved;
		};
		__le16	wCount;
	};
} ;

''', packed=True)


ffibuilder.cdef('''
/* linux/usb/functionfs.h */

struct usb_ext_compat_desc {
	__u8	bFirstInterfaceNumber;
	__u8	Reserved1;
	__u8	CompatibleID[8];
	__u8	SubCompatibleID[8];
	__u8	Reserved2[6];
} ;
''')


ffibuilder.cdef('''
/* linux/usb/functionfs.h */

struct usb_ext_prop_desc {
	__le32	dwSize;
	__le32	dwPropertyDataType;
	__le16	wPropertyNameLength;
} ;

struct usb_functionfs_strings_head {
	__le32 magic;
	__le32 length;
	__le32 str_count;
	__le32 lang_count;
} ;

enum usb_functionfs_event_type {
	FUNCTIONFS_BIND,
	FUNCTIONFS_UNBIND,

	FUNCTIONFS_ENABLE,
	FUNCTIONFS_DISABLE,

	FUNCTIONFS_SETUP,

	FUNCTIONFS_SUSPEND,
	FUNCTIONFS_RESUME
};

struct usb_functionfs_event {
	union {
		/* SETUP: packet; DATA phase i/o precedes next event
		 *(setup.bmRequestType & USB_DIR_IN) flags direction */
		struct usb_ctrlrequest	setup;
	}  u;

	/* enum usb_functionfs_event_type */
	__u8				type;
	__u8				_pad[3];
} ;


/* Endpoint ioctls */
/* The same as in gadgetfs */

/* IN transfers may be reported to the gadget driver as complete
 *	when the fifo is loaded, before the host reads the data;
 * OUT transfers may be reported to the host's "client" driver as
 *	complete when they're sitting in the FIFO unread.
 * THIS returns how many bytes are "unclaimed" in the endpoint fifo
 * (needed for precise fault handling, when the hardware allows it)
 */
#define	FUNCTIONFS_FIFO_STATUS	...

/* discards any unclaimed data in the fifo. */
#define	FUNCTIONFS_FIFO_FLUSH	...

/* resets endpoint halt+toggle; used to implement set_interface.
 * some hardware (like pxa2xx) can't support this.
 */
#define	FUNCTIONFS_CLEAR_HALT	...

/* Specific for functionfs */

/*
 * Returns reverse mapping of an interface.  Called on EP0.  If there
 * is no such interface returns -EDOM.  If function is not active
 * returns -ENODEV.
 */
#define	FUNCTIONFS_INTERFACE_REVMAP	...

/*
 * Returns real bEndpointAddress of an endpoint.  If function is not
 * active returns -ENODEV.
 */
#define	FUNCTIONFS_ENDPOINT_REVMAP	...

/*
 * Returns endpoint descriptor. If function is not active returns -ENODEV.
 */
#define	FUNCTIONFS_ENDPOINT_DESC ...

''', packed=True)

ffibuilder.cdef('''
struct descriptors {
	struct usb_functionfs_descs_head_v2 header;
	__le32 fs_count;
	__le32 hs_count;
	struct speed_descs {
		struct usb_interface_descriptor intf;
		struct usb_endpoint_descriptor_no_audio frames;
		struct usb_endpoint_descriptor_no_audio events;
	} fs_descs, hs_descs;
} ;

struct strings {
	struct usb_functionfs_strings_head header;
	struct lang {
		__le16 code;
		char str1[15];
	} lang0;
};


''', packed=True)


ffibuilder.set_source(
    'notare.gadget._usb',
    '''
    #include <linux/usb/functionfs.h>

struct descriptors {
	struct usb_functionfs_descs_head_v2 header;
	__le32 fs_count;
	__le32 hs_count;
	struct speed_descs {
		struct usb_interface_descriptor intf;
		struct usb_endpoint_descriptor_no_audio frames;
		struct usb_endpoint_descriptor_no_audio events;
	}  __attribute__((packed))  fs_descs, hs_descs;
}  __attribute__((packed)) ;


struct strings {
	struct usb_functionfs_strings_head header;
	struct lang {
		__le16 code;
		char str1[15];
	} __attribute__((packed)) lang0;
} __attribute__((packed));

    ''', include_dirs=[os.path.join(os.path.dirname(__file__), 'headers')]
)
