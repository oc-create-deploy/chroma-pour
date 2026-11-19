"""Drive normal native touch input; QA snapshots are read-only observations."""
import json, os, pathlib, subprocess, time
out = pathlib.Path('screenshots'); out.mkdir(exist_ok=True)
udid = os.environ['UDID']; bundle = os.environ['APP_BUNDLE_ID']
container = pathlib.Path(subprocess.check_output(['xcrun','simctl','get_app_container',udid,bundle,'data'],text=True).strip())
seq = 0
import importlib.util
spec=importlib.util.spec_from_file_location('touchbridge',pathlib.Path(__file__).with_name('native-touch-bridge.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
bridge=module.TouchBridge(out,udid,bundle)

def state():
    deadline = time.time()+90
    while time.time()<deadline:
        for p in container.rglob('qa-state.json'):
            try:
                s=json.loads(p.read_text())
                assert not s['errors'],s['errors']
                return s
            except (json.JSONDecodeError,FileNotFoundError): pass
        time.sleep(.5)
    probe_errors=list(container.rglob('qa-recorder-error.txt'))
    if probe_errors:
        detail=probe_errors[0].read_text()
        (out/'qa-recorder-error.txt').write_text(detail)
        raise AssertionError('Native diagnostic recorder failed: '+detail)
    raise AssertionError('Read-only native snapshot missing')

def capture(label):
    (out/(label+'.json')).write_text(json.dumps(state(),indent=2))
    subprocess.run(['xcrun','simctl','io',udid,'screenshot',str(out/(label+'.png'))],check=True)

def point(item):
    assert 0<item['x']<1 and 0<item['y']<1,item
    return f"{round(item['x']*100)}%, {round(item['y']*100)}%"

def swipe_point(item):
    return f"{item['x']*100:.4f}%, {item['y']*100:.4f}%"

def action(body):
    global seq
    seq+=1
    p=out/f'input-{seq:03}.yaml'
    p.write_text(f'appId: {bundle}\n---\n'+body+'\n')
    bridge.action(body)
    time.sleep(1)

def tap(text):
    choices=[i for i in state()['items'] if i['kind']=='button' and i['interactable'] and text.casefold() in (i.get('text','').strip().casefold(),i['name'].strip().casefold())]
    assert choices,('Button missing',text)
    action('- tapOn:\n    point: "'+point(choices[0])+'"')


def tubes(): return sorted([i for i in state()['items'] if i['kind']=='tube'],key=lambda i:i['name'])
def board(): return tuple(tuple(i['colors']) for i in tubes())
def solved(b): return all(not t or len(t)==4 and len(set(t))==1 for t in b)
def move(b,i,j):
    if i==j or not b[i] or len(b[j])==4 or b[j] and b[j][0]!=b[i][0]:return None
    n=0
    for c in b[i]:
        if c!=b[i][0]:break
        n+=1
    n=min(n,4-len(b[j]));r=list(b);r[j]=b[i][:n]+b[j];r[i]=b[i][n:];return tuple(r)
def solve(initial):
    seen=set();stack=[(initial,[])]
    while stack:
        b,path=stack.pop();key=tuple(sorted(b))
        if key in seen:continue
        seen.add(key)
        if solved(b):return path
        assert len(seen)<300000,'Solver budget exceeded'
        for i in range(len(b)):
            if not b[i] or len(set(b[i]))==1 and len(b[i])==4:continue
            empty=False
            for j in range(len(b)):
                if not b[j]:
                    if empty:continue
                    empty=True
                nxt=move(b,i,j)
                if nxt and tuple(sorted(nxt)) not in seen:stack.append((nxt,path+[(i,j)]))
    raise AssertionError('Normal generated puzzle has no solution')
def touch(i):
    action('- tapOn:\n    point: "'+point(tubes()[i])+'"')
def await_board(expected,label):
    end=time.time()+30
    while time.time()<end:
        if board()==expected:return
        time.sleep(.5)
    capture('failure-'+label);raise AssertionError(('Native pour mismatch',label,expected,board()))
capture('01-board');initial=board();liquid_total=sum(map(len,initial));palette=set(c for t in initial for c in t);assert len(initial)>=len(palette)+2 and liquid_total==4*len(palette),initial
# Full destination is illegal and must conserve every color.
full=[i for i,t in enumerate(initial) if len(t)==4]
touch(full[0]);touch(full[1]);time.sleep(2);assert board()==initial,'Illegal pour changed board'
capture('02-invalid')
path=solve(initial);assert path,'Puzzle already solved'
for turn,(i,j) in enumerate(path):
    expected=move(board(),i,j);touch(i);touch(j);await_board(expected,str(turn));time.sleep(2)
    if turn==0:
        capture('03-poured')
        subprocess.run(['xcrun','simctl','terminate',udid,bundle],check=True)
        for p in container.rglob('qa-state.json'):p.unlink()
        subprocess.run(['xcrun','simctl','launch',udid,bundle,'--playabilityQA'],check=True)
        await_board(expected,'relaunch');capture('04-restored')
    if turn%8==0:capture(f'05-progress-{turn:02}')
assert solved(board()),'Native puzzle not solved';capture('06-solved')
assert any(i['kind']=='text' and 'Clear' in i.get('text','') for i in state()['items']),'Win panel not visible'
tap('Refresh');time.sleep(2)
assert sum(map(len,board()))==liquid_total and not solved(board()),'Refresh did not create new puzzle'
capture('07-reset')
(out/'result.json').write_text(json.dumps({'nativePours':len(path),'invalidPourConserved':True,'relaunchPersisted':True,'solved':True,'reset':True},indent=2))
