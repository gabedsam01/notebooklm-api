import notebooklm
print("notebooklm API:")
for name in dir(notebooklm):
    if not name.startswith('_'):
        obj = getattr(notebooklm, name)
        print(f"  {name}: {type(obj).__name__}")
