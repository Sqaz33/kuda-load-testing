import paramiko,sys,os,base64,pathlib,hashlib
ssh=paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('192.168.0.213',username='mset6',password=os.environ['KUDA_SSH_PASSWORD'],timeout=15,look_for_keys=False,allow_agent=False)
mode=sys.argv[1]
if mode=='ps':
 code=pathlib.Path(sys.argv[2]).read_text(encoding='utf-8-sig')
 cmd='powershell -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(code.encode('utf-16le')).decode()
 if len(cmd)>7000:
  folder='C:/Users/mset6/kuda-nt/scripts'
  sftp=ssh.open_sftp()
  try:sftp.mkdir(folder)
  except OSError:pass
  remote=folder+'/'+pathlib.Path(sys.argv[2]).stem+'-'+hashlib.sha256(code.encode()).hexdigest()[:12]+'.ps1'
  with sftp.open(remote,'wb') as f:f.write(b'\xef\xbb\xbf'+code.encode('utf8'))
  sftp.close()
  cmd='powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "'+remote+'"'
 _,out,err=ssh.exec_command(cmd,timeout=600)
 print(out.read().decode('utf8',errors='replace'))
 print(err.read().decode('utf8',errors='replace'))
 status=out.channel.recv_exit_status()
 print('EXIT',status)
 if status:
  ssh.close()
  sys.exit(status)
elif mode=='run':
 _,out,err=ssh.exec_command(sys.argv[2],timeout=180)
 print(out.read().decode('utf8',errors='replace'));print(err.read().decode('utf8',errors='replace'))
elif mode in ('put','get'):
 sftp=ssh.open_sftp()
 getattr(sftp,mode)(sys.argv[2],sys.argv[3])
 print('Transferred')
ssh.close()
