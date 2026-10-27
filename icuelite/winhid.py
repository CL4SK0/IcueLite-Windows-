"""Accès HID natif Windows (hid.dll + setupapi.dll) via ctypes.

Remplace le module compilé hidapi : rien à installer, marche avec toutes les versions de Python.
Expose la même interface que l'usage qu'en fait devices.py : enumerate() et Transport.
"""

import ctypes
import re
from ctypes import wintypes

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x01
FILE_SHARE_WRITE = 0x02
OPEN_EXISTING = 3
FILE_FLAG_OVERLAPPED = 0x40000000
WAIT_OBJECT_0 = 0
ERROR_IO_PENDING = 997
DIGCF_PRESENT = 0x02
DIGCF_DEVICEINTERFACE = 0x10
DIGCF_ALLCLASSES = 0x04
ERROR_INSUFFICIENT_BUFFER = 122
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_hid = ctypes.WinDLL("hid", use_last_error=True)
_setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("InterfaceClassGuid", GUID),
                ("Flags", wintypes.DWORD), ("Reserved", ctypes.c_size_t)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wintypes.ULONG), ("VendorID", wintypes.USHORT),
                ("ProductID", wintypes.USHORT), ("VersionNumber", wintypes.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [("Usage", wintypes.USHORT), ("UsagePage", wintypes.USHORT),
                ("InputReportByteLength", wintypes.USHORT), ("OutputReportByteLength", wintypes.USHORT),
                ("FeatureReportByteLength", wintypes.USHORT), ("Reserved", wintypes.USHORT * 17),
                ("NumberLinkCollectionNodes", wintypes.USHORT),
                ("NumberInputButtonCaps", wintypes.USHORT), ("NumberInputValueCaps", wintypes.USHORT),
                ("NumberInputDataIndices", wintypes.USHORT),
                ("NumberOutputButtonCaps", wintypes.USHORT), ("NumberOutputValueCaps", wintypes.USHORT),
                ("NumberOutputDataIndices", wintypes.USHORT),
                ("NumberFeatureButtonCaps", wintypes.USHORT), ("NumberFeatureValueCaps", wintypes.USHORT),
                ("NumberFeatureDataIndices", wintypes.USHORT)]


def _proto(dll, name, restype, *argtypes):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = restype, list(argtypes)
    return fn


HANDLE = wintypes.HANDLE
PVOID = ctypes.c_void_p

HidD_GetHidGuid = _proto(_hid, "HidD_GetHidGuid", None, ctypes.POINTER(GUID))
HidD_GetAttributes = _proto(_hid, "HidD_GetAttributes", wintypes.BOOLEAN, HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES))
HidD_GetPreparsedData = _proto(_hid, "HidD_GetPreparsedData", wintypes.BOOLEAN, HANDLE, ctypes.POINTER(PVOID))
HidD_FreePreparsedData = _proto(_hid, "HidD_FreePreparsedData", wintypes.BOOLEAN, PVOID)
HidP_GetCaps = _proto(_hid, "HidP_GetCaps", ctypes.c_long, PVOID, ctypes.POINTER(HIDP_CAPS))
HidD_GetProductString = _proto(_hid, "HidD_GetProductString", wintypes.BOOLEAN, HANDLE, PVOID, wintypes.ULONG)
HidD_SetFeature = _proto(_hid, "HidD_SetFeature", wintypes.BOOLEAN, HANDLE, PVOID, wintypes.ULONG)
HidD_GetFeature = _proto(_hid, "HidD_GetFeature", wintypes.BOOLEAN, HANDLE, PVOID, wintypes.ULONG)
HidD_SetOutputReport = _proto(_hid, "HidD_SetOutputReport", wintypes.BOOLEAN, HANDLE, PVOID, wintypes.ULONG)

SetupDiGetClassDevsW = _proto(_setupapi, "SetupDiGetClassDevsW", HANDLE,
                              ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD)
SetupDiEnumDeviceInterfaces = _proto(_setupapi, "SetupDiEnumDeviceInterfaces", wintypes.BOOL,
                                     HANDLE, PVOID, ctypes.POINTER(GUID), wintypes.DWORD,
                                     ctypes.POINTER(SP_DEVICE_INTERFACE_DATA))
SetupDiGetDeviceInterfaceDetailW = _proto(_setupapi, "SetupDiGetDeviceInterfaceDetailW", wintypes.BOOL,
                                          HANDLE, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), PVOID,
                                          wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), PVOID)
class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("ClassGuid", GUID), ("DevInst", wintypes.DWORD),
                ("Reserved", ctypes.c_size_t)]


SetupDiEnumDeviceInfo = _proto(_setupapi, "SetupDiEnumDeviceInfo", wintypes.BOOL, HANDLE, wintypes.DWORD,
                               ctypes.POINTER(SP_DEVINFO_DATA))
SetupDiGetDeviceInstanceIdW = _proto(_setupapi, "SetupDiGetDeviceInstanceIdW", wintypes.BOOL, HANDLE,
                                     ctypes.POINTER(SP_DEVINFO_DATA), wintypes.LPWSTR, wintypes.DWORD,
                                     ctypes.POINTER(wintypes.DWORD))
SetupDiDestroyDeviceInfoList = _proto(_setupapi, "SetupDiDestroyDeviceInfoList", wintypes.BOOL, HANDLE)

CreateFileW = _proto(_kernel32, "CreateFileW", HANDLE, wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                     PVOID, wintypes.DWORD, wintypes.DWORD, HANDLE)
CloseHandle = _proto(_kernel32, "CloseHandle", wintypes.BOOL, HANDLE)
WriteFile = _proto(_kernel32, "WriteFile", wintypes.BOOL, HANDLE, PVOID, wintypes.DWORD,
                   ctypes.POINTER(wintypes.DWORD), PVOID)
ReadFile = _proto(_kernel32, "ReadFile", wintypes.BOOL, HANDLE, PVOID, wintypes.DWORD,
                  ctypes.POINTER(wintypes.DWORD), PVOID)
CreateEventW = _proto(_kernel32, "CreateEventW", HANDLE, PVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR)
WaitForSingleObject = _proto(_kernel32, "WaitForSingleObject", wintypes.DWORD, HANDLE, wintypes.DWORD)
GetOverlappedResult = _proto(_kernel32, "GetOverlappedResult", wintypes.BOOL, HANDLE, PVOID,
                             ctypes.POINTER(wintypes.DWORD), wintypes.BOOL)
CancelIo = _proto(_kernel32, "CancelIo", wintypes.BOOL, HANDLE)
HidD_FlushQueue = _proto(_hid, "HidD_FlushQueue", wintypes.BOOLEAN, HANDLE)


class OVERLAPPED(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD), ("hEvent", HANDLE)]


def _error(what):
    code = ctypes.get_last_error()
    return OSError(code, f"{what} : {ctypes.FormatError(code).strip()} (code {code})")


def _open(path, access, flags=0):
    handle = CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, flags, None)
    if handle is None or handle == INVALID_HANDLE_VALUE:
        raise _error("ouverture")
    return handle


def _caps(handle):
    pre = PVOID()
    if not HidD_GetPreparsedData(handle, ctypes.byref(pre)):
        return None
    try:
        caps = HIDP_CAPS()
        HidP_GetCaps(pre, ctypes.byref(caps))
        return caps
    finally:
        HidD_FreePreparsedData(pre)


def _interface_paths():
    guid = GUID()
    HidD_GetHidGuid(ctypes.byref(guid))
    info = SetupDiGetClassDevsW(ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    if info is None or info == INVALID_HANDLE_VALUE:
        raise _error("liste des périphériques HID")
    try:
        index = 0
        while True:
            data = SP_DEVICE_INTERFACE_DATA()
            data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            if not SetupDiEnumDeviceInterfaces(info, None, ctypes.byref(guid), index, ctypes.byref(data)):
                break
            index += 1
            required = wintypes.DWORD()
            SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(data), None, 0, ctypes.byref(required), None)
            if not required.value:
                continue
            buf = ctypes.create_string_buffer(required.value)
            # cbSize de SP_DEVICE_INTERFACE_DETAIL_DATA_W : 8 en 64 bits, 6 en 32 bits
            ctypes.cast(buf, ctypes.POINTER(wintypes.DWORD))[0] = 8 if ctypes.sizeof(PVOID) == 8 else 6
            if not SetupDiGetDeviceInterfaceDetailW(info, ctypes.byref(data), buf, required, None, None):
                continue
            yield ctypes.wstring_at(ctypes.addressof(buf) + 4)
    finally:
        SetupDiDestroyDeviceInfoList(info)


def usb_devices(vendor_id):
    """Identifiants des appareils USB présents de ce fabricant, HID ou non : [(PID, identifiant d'instance)].

    Sert pour les appareils qui ne passent pas par le pilote HID de Windows (l'AX1600i, par exemple,
    utilise le pilote USBXpress de Corsair)."""
    info = SetupDiGetClassDevsW(None, "USB", None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
    if info is None or info == INVALID_HANDLE_VALUE:
        raise _error("liste des périphériques USB")
    found = []
    try:
        index = 0
        while True:
            data = SP_DEVINFO_DATA()
            data.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            if not SetupDiEnumDeviceInfo(info, index, ctypes.byref(data)):
                break
            index += 1
            buf = ctypes.create_unicode_buffer(512)
            if not SetupDiGetDeviceInstanceIdW(info, ctypes.byref(data), buf, len(buf), None):
                continue
            match = re.search(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", buf.value, re.IGNORECASE)
            if match and int(match.group(1), 16) == vendor_id:
                found.append((int(match.group(2), 16), buf.value))
    finally:
        SetupDiDestroyDeviceInfoList(info)
    return found


def enumerate(vendor_id=0, product_id=0):
    """Même format de résultat que hid.enumerate() du module hidapi."""
    devices = []
    for path in _interface_paths():
        # Accès 0 : suffit pour lire les attributs, même sur une souris ou un clavier verrouillés par Windows
        try:
            handle = _open(path, 0)
        except OSError:
            continue
        try:
            attrs = HIDD_ATTRIBUTES()
            attrs.Size = ctypes.sizeof(HIDD_ATTRIBUTES)
            if not HidD_GetAttributes(handle, ctypes.byref(attrs)):
                continue
            if vendor_id and attrs.VendorID != vendor_id:
                continue
            if product_id and attrs.ProductID != product_id:
                continue
            caps = _caps(handle)
            name = ctypes.create_unicode_buffer(128)
            product = name.value if HidD_GetProductString(handle, name, ctypes.sizeof(name)) else ""
            match = re.search(r"&mi_([0-9a-f]{2})", path, re.IGNORECASE)
            devices.append({
                "path": path,
                "vendor_id": attrs.VendorID,
                "product_id": attrs.ProductID,
                "interface_number": int(match.group(1), 16) if match else -1,
                "usage_page": caps.UsagePage if caps else 0,
                "usage": caps.Usage if caps else 0,
                "feature_report_length": caps.FeatureReportByteLength if caps else 0,
                "output_report_length": caps.OutputReportByteLength if caps else 0,
                "input_report_length": caps.InputReportByteLength if caps else 0,
                "product_string": product,
            })
        finally:
            CloseHandle(handle)
    return devices


class Transport:
    def __init__(self, path):
        self.path = path
        self.reader = None
        self.access = "lecture/écriture"
        try:
            self.handle = _open(path, GENERIC_READ | GENERIC_WRITE)
        except OSError as exc:
            # Windows réserve les collections souris/clavier : un accès 0 suffit pour les feature reports
            self.handle = _open(path, 0)
            self.access = f"limité ({exc})"
        caps = _caps(self.handle)
        self.feature_len = caps.FeatureReportByteLength if caps else 0
        self.output_len = caps.OutputReportByteLength if caps else 0
        self.input_len = caps.InputReportByteLength if caps else 0

    def _pad(self, data, length):
        data = bytes(data)
        return data + bytes(max(0, length - len(data)))

    def send_feature(self, data):
        buf = ctypes.create_string_buffer(self._pad(data, self.feature_len), max(len(data), self.feature_len))
        if not HidD_SetFeature(self.handle, buf, len(buf)):
            raise _error("envoi")
        return len(data)

    def get_feature(self, length):
        size = max(length, self.feature_len)
        buf = ctypes.create_string_buffer(size)  # octet 0 = report ID 0
        if not HidD_GetFeature(self.handle, buf, size):
            raise _error("lecture")
        return buf.raw

    def write(self, data):
        payload = self._pad(data, self.output_len)
        buf = ctypes.create_string_buffer(payload, len(payload))
        written = wintypes.DWORD()
        if not WriteFile(self.handle, buf, len(payload), ctypes.byref(written), None):
            first = ctypes.get_last_error()
            # Certains casques n'acceptent que HidD_SetOutputReport
            if not HidD_SetOutputReport(self.handle, buf, len(payload)):
                exc = _error("écriture")
                raise OSError(exc.errno, f"{exc.strerror} ; WriteFile : code {first}")
            return len(data)
        return len(data)

    def read(self, timeout_ms=500):
        """Prochain rapport d'entrée (octet 0 = report ID), ou b"" si rien n'arrive à temps."""
        if self.reader is None:
            # Poignée à part, en mode asynchrone : c'est ce qui permet d'abandonner la lecture après un délai
            self.reader = _open(self.path, GENERIC_READ | GENERIC_WRITE, FILE_FLAG_OVERLAPPED)
            self.event = CreateEventW(None, True, False, None)
        size = max(self.input_len, 1)
        buf = ctypes.create_string_buffer(size)
        ov = OVERLAPPED()
        ov.hEvent = self.event
        got = wintypes.DWORD()
        if not ReadFile(self.reader, buf, size, ctypes.byref(got), ctypes.byref(ov)):
            if ctypes.get_last_error() != ERROR_IO_PENDING:
                raise _error("lecture")
            if WaitForSingleObject(self.event, timeout_ms) != WAIT_OBJECT_0:
                CancelIo(self.reader)
                GetOverlappedResult(self.reader, ctypes.byref(ov), ctypes.byref(got), True)
                return b""
            if not GetOverlappedResult(self.reader, ctypes.byref(ov), ctypes.byref(got), False):
                raise _error("lecture")
        return buf.raw[:got.value]

    def flush(self):
        """Oublie les rapports d'entrée en attente (réponses périmées)."""
        if self.reader is not None:
            HidD_FlushQueue(self.reader)

    def close(self):
        for name in ("reader", "handle"):
            handle = getattr(self, name, None)
            if handle:
                CloseHandle(handle)
                setattr(self, name, None)
        if getattr(self, "event", None):
            CloseHandle(self.event)
            self.event = None
