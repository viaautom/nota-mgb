import os, sys, glob
from lxml import etree
XSD = sys.argv[1]
class Local(etree.Resolver):
    def resolve(self, url, pubid, ctx):
        for pre in ("https://", "http://"):
            if url.startswith(pre):
                rest = url[len(pre):].replace("standards.iso.org/iso/19115/-3/", "schemas.isotc211.org/19115/-3/")
                path = os.path.join(XSD, rest)
                if os.path.exists(path):
                    return self.resolve_filename(path, ctx)
        return None
parser = etree.XMLParser(no_network=True); parser.resolvers.add(Local())
schema = etree.XMLSchema(etree.parse(os.path.join(XSD, "schemas.isotc211.org/19115/-3/mds/2.0/mds.xsd"), parser))
for f in sys.argv[2:]:
    doc = etree.parse(f)
    ok = schema.validate(doc)
    print("OK  " if ok else "ERRO", os.path.basename(f))
    for e in list(schema.error_log)[:8]: print("    linha", e.line, e.message[:200])
