import datetime,json,pathlib,subprocess
out=pathlib.Path('results/final_202611/B_nov09');out.mkdir(parents=True,exist_ok=True)
command=['ssh','-S','/tmp/dsa5208-vanda-e1561365.sock','-o','BatchMode=yes','-o','ConnectTimeout=8','e1561365@vanda.nus.edu.sg','qstat -Q']
r=subprocess.run(command,text=True,capture_output=True,timeout=25)
record={'time_singapore':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'submission_performed':False}
(out/'scheduler_health.json').write_text(json.dumps(record,indent=2));print(json.dumps(record,indent=2))
