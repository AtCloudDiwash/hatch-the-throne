import json,os,sys,time
name=sys.argv[1]; d=json.load(sys.stdin); log=os.path.join(d["cwd"],"hooklog.jsonl")
def rec(**k):
    open(log,"a").write(json.dumps(dict(hook=name,t=round(time.time(),2),keys=sorted(d),env_root=bool(os.environ.get("CLAUDE_PLUGIN_ROOT")),env_data=bool(os.environ.get("CLAUDE_PLUGIN_DATA")),**k))+"\n")
fp=d.get("tool_input",{}).get("file_path",""); b=os.path.basename(fp)
if name=="session":
    rec(source=d.get("source")); print(json.dumps({"systemMessage":"LGTOKEN-SESSIONSYS","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"LGTOKEN-SESSIONCTX"}}))
elif name=="prompt":
    rec(); print(json.dumps({"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"LGTOKEN-PROMPTCTX"}}))
elif name=="pre":
    rec(file=b,tool=d.get("tool_name"),pm=d.get("permission_mode"))
    o={"hookEventName":"PreToolUse"}
    if b=="ctx.txt": o.update(permissionDecision="allow",additionalContext="LGTOKEN-PRECTX")
    if b=="deny.txt": o.update(permissionDecision="deny",permissionDecisionReason="LGTOKEN-DENYREASON",additionalContext="LGTOKEN-DENYCTX")
    if b=="ask.txt": o.update(permissionDecision="ask",permissionDecisionReason="LGTOKEN-ASKREASON",additionalContext="LGTOKEN-ASKCTX")
    print(json.dumps({"hookSpecificOutput":o}))
elif name=="rewake":
    rec(file=b,start=True); time.sleep(2)
    if b=="rewake.txt":
        rec(file=b,exit=2); sys.stderr.write("LGTOKEN-REWAKE-STDERR"); sys.exit(2)
elif name=="async":
    rec(file=b); time.sleep(1)
    if b=="rewake.txt": print(json.dumps({"systemMessage":"LGTOKEN-ASYNCSYS","hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"LGTOKEN-ASYNCCTX"}}))
elif name=="stop":
    rec(active=d.get("stop_hook_active"),last=(d.get("last_assistant_message") or "")[:80])
    if not d.get("stop_hook_active"):
        print(json.dumps({"decision":"block","reason":"LGTOKEN-STOPREASON. Write stopped.txt, then finish."}))
    else: print(json.dumps({"systemMessage":"LGTOKEN-STOPSYS"}))
