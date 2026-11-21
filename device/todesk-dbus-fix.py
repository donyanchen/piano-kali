import sys
import lief

src, dst = sys.argv[1], sys.argv[2]
ef = lief.ELF.parse(src)
if ef is None:
    sys.exit("parse failed")

n = 0
for sym in ef.dynamic_symbols:
    name = sym.name or ""
    if name.startswith("dbus_") or name.startswith("_dbus_"):
        try:
            sym.binding = lief.ELF.Symbol.BINDING.LOCAL
            n += 1
        except Exception:
            pass

ef.write(dst)
print("localized %d dbus symbols -> %s" % (n, dst))
