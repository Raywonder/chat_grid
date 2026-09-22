import {afterEach,describe,expect,it,vi} from 'vitest';
import {createAuthController} from './authController';
import {SignalingClient} from '../network/signalingClient';

afterEach(()=>vi.unstubAllGlobals());
describe('explicit handoff and welcome ordering',()=>{
 it('marks only an active explicit attempt, then resumes ordinary cookie transport',async()=>{
  let explicit=true;
  const urls:string[]=[];
  const sockets: Array<{onopen: null|(()=>void);readyState:number;close:()=>void}> = [];
  class Socket {
   static OPEN=1;readyState=0;onopen=null;onmessage=null;onerror=null;onclose=null;
   constructor(url:string){urls.push(url);sockets.push(this);}
   close(){this.readyState=3;}
  }
  vi.stubGlobal('WebSocket',Socket);vi.stubGlobal('window',{setTimeout,clearTimeout});
  const client=new SignalingClient('wss://fixture.invalid/indiginous/ws',vi.fn(),()=>explicit);
  const first=client.connect(vi.fn());sockets[0].readyState=1;sockets[0].onopen?.();await first;
  expect(new URL(urls[0]).searchParams.get('auth_mode')).toBe('external');
  expect(urls[0]).not.toContain('assertion');client.disconnect();explicit=false;
  const next=client.connect(vi.fn());sockets[1].readyState=1;sockets[1].onopen?.();await next;
  expect(new URL(urls[1]).search).toBe('');client.disconnect();
 });
 it('does not overwrite world status when cookie persistence completes after welcome',async()=>{
  let running=false;let finish!: (value:Response)=>void;
  vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(resolve=>{finish=resolve;})));
  vi.stubGlobal('sessionStorage',{removeItem:vi.fn()});
  const classList={add:vi.fn(),remove:vi.fn(),toggle:vi.fn()};
  vi.stubGlobal('document',{body:{classList}});
  const status=vi.fn();const noop=vi.fn();const element={classList};
  const deps={dom:{loginView:element,authSessionView:element,authSessionText:element,signInButton:element,connectButton:element,guestButton:element,logoutButton:element},initialAuthUsername:'fixture',initialExternalAuthAssertion:'synthetic',isRunning:()=>running,isMuted:()=>true,isConnecting:()=>false,setConnecting:noop,applyMuteToTrack:noop,signalingSend:noop,disconnect:noop,saveAuthUsername:noop,setConnectionStatus:status,updateStatus:noop,pushChatMessage:noop,onServerAdminMenuActions:noop,authSessionCookieSetUrl:'/fixture',authSessionCookieClientHeader:'fixture'} as unknown as Parameters<typeof createAuthController>[0];
  deps.disconnect=vi.fn();
  const controller=createAuthController(deps);
  const pending=controller.handleAuthResult({type:'auth_result',ok:true,message:'fixture',sessionToken:'synthetic-fixture',username:'fixture',role:'user',permissions:[]});
  running=true;finish({ok:true} as Response);await pending;
  expect(status).not.toHaveBeenCalled();expect(deps.disconnect).not.toHaveBeenCalled();
 });
});

