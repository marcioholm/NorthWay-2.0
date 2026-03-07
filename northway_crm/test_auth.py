import urllib.request
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request("https://crm.northwaycompany.com.br/login", headers={'User-Agent': 'Mozilla/5.0'})
try:
    response = urllib.request.urlopen(req, context=ctx)
    html = response.read().decode('utf-8')
    import re
    errors = re.findall(r'Exception(.*?)\<', html)
    print("Errors found:", errors)
except Exception as e:
    print(e)
