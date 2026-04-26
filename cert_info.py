import socket
import ssl

host = "aws-1-us-east-2.pooler.supabase.com"
port = 6543
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
s = socket.socket()
s.settimeout(8)
try:
    s.connect((host, port))
    ss = ctx.wrap_socket(s, server_hostname=host)
    cert = ss.getpeercert()
    print("cert subject:", cert.get("subject"))
    print("issuer:", cert.get("issuer"))
    print("notAfter:", cert.get("notAfter"))
    ss.close()
except Exception as e:
    print("Exception:", e)
finally:
    try:
        s.close()
    except:
        pass
