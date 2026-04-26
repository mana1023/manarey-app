import socket
import ssl

for port in (5432, 6543):
    host = "aws-1-us-east-2.pooler.supabase.com"
    print("\nProbing", host, port)
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(8)
        s.connect((host, port))
        print("TCP connected")
        ss = context.wrap_socket(s, server_hostname=host)
        print("SSL version:", ss.version())
        print("cipher:", ss.cipher())
        ss.close()
    except Exception as e:
        print("Exception:", repr(e))
    finally:
        try:
            s.close()
        except:
            pass
