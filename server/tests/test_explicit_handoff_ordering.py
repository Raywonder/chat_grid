import asyncio,base64,hashlib,hmac,importlib.util,json,pathlib,sys,tempfile,time,types,uuid
from app.server import SignalingServer as Original
from app.auth_service import AuthService,AuthError
from app.models import AuthExternalPacket,AuthResumePacket
mod=types.SimpleNamespace(SignalingServer=Original)
def sign(subject):
 payload={'aud':'chatgrid','provider':'fixture','sub':subject,'username':subject,'role':'user','nonce':str(uuid.uuid4()),'iat':int(time.time()),'exp':int(time.time())+120}
 enc=base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
 return enc+'.'+base64.urlsafe_b64encode(hmac.new(b'fixture-secret',enc.encode(),hashlib.sha256).digest()).decode().rstrip('=')
class Socket:
 def __init__(self,path,assertion):self.request=types.SimpleNamespace(path=path);self.assertion=assertion
 def __aiter__(self):return self
 async def __anext__(self):
  if self.assertion is None:raise StopAsyncIteration
  a=self.assertion;self.assertion=None;return a
 async def close(self):pass
async def run_case(cls,marker,assertion):
 with tempfile.TemporaryDirectory(prefix='indiginous-auth-fixture-') as temp:
  auth=AuthService(db_path=pathlib.Path(temp)/'fixture.sqlite',token_hash_secret='fixture-secret',password_min_length=8,password_max_length=32,username_min_length=2,username_max_length=32)
  cookie=auth.login_external_assertion(sign('alpha'),signing_secret='fixture-secret')
  server=object.__new__(cls);server.clients={};server.websocket_path='/ws';server.grid_name='fixture';server.welcome_message='fixture';server.release_version='fixture';server.server_version='fixture'
  server._session_token_from_websocket_cookie=lambda ws:cookie.token
  server._auth_policy=lambda:{};server._current_expected_client_revision=lambda:'fixture'
  output=[];identities=[]
  async def send(ws,packet):output.append((packet.type,getattr(packet,'ok',None),getattr(packet,'message','')))
  server._send=send
  async def handle(client,packet):
   if client.authenticated:
    return await Original._handle_auth_packet(server,client,packet)
   try:
    session=auth.resume(packet.sessionToken) if isinstance(packet,AuthResumePacket) else auth.login_external_assertion(packet.assertion,signing_secret='fixture-secret')
    client.authenticated=True;identities.append(session.user.username);output.append(('auth_result',True,''))
   except AuthError:output.append(('auth_result',False,'verified rejection'))
   return True
  async def message(client,assertion):await handle(client,AuthExternalPacket(type='auth_external',assertion=assertion))
  server._handle_auth_packet=handle;server._handle_message=message
  await cls._handle_client(server,Socket('/ws'+marker,assertion));auth.close()
  return output,identities
async def main():
 for label,marker,assertion,expected in [('cookie only','',None,'alpha'),('same account','?auth_mode=external',sign('alpha'),'alpha'),('different account','?auth_mode=external',sign('beta'),'beta')]:
  out,ids=await run_case(mod.SignalingServer,marker,assertion);assert ids==[expected] and not any(ok is False for _,ok,_ in out);print('PASS',label)
 out,ids=await run_case(mod.SignalingServer,'?auth_mode=external','invalid-fixture');assert ids==[] and any(ok is False for _,ok,_ in out);print('PASS invalid explicit assertion never falls back to cookie')
 out,ids=await run_case(mod.SignalingServer,'?auth_mode=external',None);assert ids==[] and any(kind=='auth_required' for kind,_,_ in out);print('PASS marker without assertion stays unauthenticated')
 print('PASS unchanged full assertion verifier used with isolated temporary fixtures; no production state or credentials')
def test_explicit_handoff_cookie_ordering():
 asyncio.run(main())

