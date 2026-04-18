import re

def is_relevant_cookie(name: str) -> bool:
    exact_names = {"SID", "HSID", "SSID", "SAPISID", "APISID", "OSID"}
    if name in exact_names:
        return True
    if name.startswith("__Secure-") and ("PSID" in name or "PAPISID" in name or "OSID" in name):
        return True
    return False

test_names = ["SID", "HSID", "__Secure-1PSID", "__Secure-3PSIDCC", "_ga", "NID", "AEC", "__Secure-ENID"]
for name in test_names:
    print(f"{name}: {is_relevant_cookie(name)}")
