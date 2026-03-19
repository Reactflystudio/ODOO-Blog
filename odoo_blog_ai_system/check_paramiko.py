try:
    import paramiko
    print("paramiko_installed")
except ImportError:
    print("paramiko_not_installed")
