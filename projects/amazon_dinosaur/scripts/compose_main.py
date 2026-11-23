#!/usr/bin/env python3
"""Original Hans Zimmer-style cinematic cue: Amazon Dinosaur - Giants Walking.
Steady 90 BPM, D major, horn hymn theme, cello cathartic ostinato, braam, timpani/taiko, choir.
No kit/guitar/synth/funk syncopation, no tempo map, no copied Williams melody."""
import json, os
HERE=os.path.dirname(os.path.abspath(__file__)); P=os.path.dirname(HERE)
BPM=90.0; BAR=4.0; BARS=44; TOTAL=BARS*BAR
# chords per bar (root midi low, chord tones)
# D, Bb, F, C, D, Bm, G, A, Dm etc as (root, [tones])
CH={
 "D":(38,[62,66,69]), "Bb":(46,[62,65,70]), "F":(41,[60,65,69]), "C":(36,[60,64,67]),
 "Bm":(47,[62,66,71]), "G":(43,[62,67,71]), "A":(45,[61,64,69]), "Dm":(38,[62,65,69]),
}
PROG=["D","A","D","G","D","Bm","G","A","D","G","F","C",
      "D","A","D","A","D","Bb","F","C","Dm","Bb","Dm","A",
      "Dm","Dm","Bb","A","Dm","Dm","Bb","C",
      "D","Bb","F","C","D","A","Bm","G","D","Bb","D","D"]
assert len(PROG)==44
def N(t,d,p,v): return {"t":float(t),"d":float(d),"p":int(p),"v":float(v)}
def bar_t(b): return b*BAR

horns=[]; strings=[]; violas=[]; celli=[]; basses=[]; piano=[]; tromb=[]; tuba=[]; trump=[]; timp=[]; taiko=[]; choir=[]; trem=[]; hit=[]
# Theme (beats within 4 bars): D-F#-A-D | C#-B-A
THEME=[(0,2,62),(2,2,66),(4,3,69),(7,1,74),(8,2,73),(10,2,74),(12,4,74)]
def add_theme(track,bar0,vel,octave=0):
    for t,d,p in THEME: track.append(N(bar_t(bar0)+t,d+0.02,p+octave,vel))
# Horns theme bars 0,8,16?,32,40 ; strings answer 4,12,36 ; full finale 40 horns+strings
add_theme(horns,0,0.72)
for _tt,_dd,_pp in [(0,2,62),(2,2,64),(4,3,66),(7,1,69),(8,2,71),(10,2,69),(12,2,64)]: horns.append(N(bar_t(8)+_tt,_dd+0.02,_pp,0.78))
for _tt,_dd,_pp in [(0,2,62),(2,2,66),(4,3,71),(7,1,74),(8,2,76),(10,2,74),(12,2,72)]: horns.append(N(bar_t(32)+_tt,_dd+0.02,_pp,0.88))
for tt,dd,pp in [(0,2,62),(2,2,66),(4,3,69),(7,1,74)]: horns.append(N(bar_t(40)+tt,dd+0.08,pp,0.95))
for b in (42,43): horns.append(N(bar_t(b),3.9,62,0.85))
# off-beat pickups (syncopation index) before each theme statement
for bar0 in (0,8,32):
    if bar0>0: horns.append(N(bar_t(bar0)-0.5,0.5,64,0.70))
    horns.append(N(bar_t(bar0)+3.5,0.5,71,0.75))
add_theme(strings,4,0.70); add_theme(strings,12,0.76); add_theme(strings,36,0.86)
# Horns fragment in chase bars 28-31: D-A
for b in range(28,32):
    root,tones=CH[PROG[b]]
    seq=[tones[2]+12,tones[1]+12,tones[2]+12,tones[1]+12]
    for i,pp in enumerate(seq): horns.append(N(bar_t(b)+i,1,pp,0.85))
for i,b in enumerate(range(24,28)):
    horns.append(N(bar_t(b),4.05,[50,50,53,50][i],0.65))
# low horn call in dread bars 20-23 varied
for i,b in enumerate(range(20,24)):
    horns.append(N(bar_t(b),2,62,0.70)); horns.append(N(bar_t(b)+2,2,57,0.70))
# Strings pad: bars 4-43 chord tones whole bar (skip last hit bar 43? keep)
THEME_BARS={4,5,6,7,12,13,14,15,36,37,38,39,40,41,42,43}
for b in range(4,44):
    root,tones=CH[PROG[b]]
    if b in THEME_BARS:
        if b>=42:
            strings.append(N(bar_t(b),3.9,62,0.68)); strings.append(N(bar_t(b),3.9,74,0.60))
        else:
            strings.append(N(bar_t(b),3.9,root+36,0.60))
        continue
    if b in list(range(8,12))+list(range(32,44)): continue
    for p in tones: strings.append(N(bar_t(b),3.9,p,0.55 if b<24 else 0.68))
# Violas counter: fifth of chord, bars 4-43
FIFTH={"D":57,"Bb":53,"F":48,"C":43,"Bm":54,"G":50,"A":52,"Dm":57}
for b in range(4,44):
    if b>=42:
        violas.append(N(bar_t(b),2.0,62,0.50)); continue
    violas.append(N(bar_t(b),4.05,CH[PROG[b]][0]+12,0.50))
# Choir: bars 0-3,8-11,32-43 chord tones (different voicing, +12)
for b in list(range(0,4))+list(range(8,12))+list(range(32,44)):
    root,tones=CH[PROG[b]]
    if b>=42:
        choir.append(N(bar_t(b),3.9,74,0.62)); continue
    for pp in tones: choir.append(N(bar_t(b),3.9,pp+12,0.55 if b<32 else 0.68))
# Basses pedal/root whole bars 0-42
for b in range(0,44):
    root,tones=CH[PROG[b]]
    _bv=0.62+0.06*((b*7)%5)+ (0.10 if b%4==0 else 0)
    # high chord roots down an octave: keep every bass fundamental below the LFE crossover for uniform LFE level
    _bp=root-12 if root>43 else root
    if b>=42: basses.append(N(bar_t(b),4.2,38,_bv))
    else: basses.append(N(bar_t(b),4.2,_bp,_bv))
# Piano hymn chords bars 0-42, chase hammer root eighths bars 32-39
for b in range(0,44):
    root,tones=CH[PROG[b]]
    if b>=42:
        piano.append(N(bar_t(b),3.8,50,0.60)); continue
    piano.append(N(bar_t(b),3.8,root,0.62))
    piano.append(N(bar_t(b),3.8,root+7,0.55))
    if 32<=b<40:
        for i in range(8): piano.append(N(bar_t(b)+i*0.5,0.45,root+24+[0,7,12,7,0,7,12,19][i],0.80))
# Celli ostinato bars 12-42 (silence bars 31 beat3-4? keep straight, silence before chase at bar31 last 2 beats omitted)
OST=[0,7,12,16,19,12,7,12]  # semitone offsets from root+? use root+12 base
for b in range(12,43):
    if b==31: 
        # only first 2 beats, then silence
        root,tones=CH[PROG[b]]
        for i in range(4): celli.append(N(bar_t(b)+i*0.5,0.45,root+12+OST[i],0.72))
        continue
    if b==39:
        root,tones=CH[PROG[b]]
        for i in range(4): celli.append(N(bar_t(b)+i*0.5,0.45,root+12+OST[i],0.85))
        continue
    root,tones=CH[PROG[b]]
    if b>=42: root=38
    vel=0.65 if b<24 else (0.78 if b<32 else 0.88)
    for i,off in enumerate(OST):
        # vary last notes every 2 bars by chord fifth
        o=off
        if i>=6 and b%2==1: o=FIFTH[PROG[b]]-root
        celli.append(N(bar_t(b)+i*0.5,0.45,root+12+o,vel))
# Tremolo dread bars 24-31: repeated chord tones eighths
for b in range(24,32):
    root,tones=CH[PROG[b]]
    for i in range(8):
        trem.append(N(bar_t(b)+i*0.5,0.45,tones[i%len(tones)]+12,0.60+0.02*i))
# Braam trombones+tuba bars 16,24,32,40 (D root/octave long)
for b in [16,24,32,40]:
    tromb.append(N(bar_t(b),3.5,50,0.88)); tromb.append(N(bar_t(b),3.5,62,0.92)); tromb.append(N(bar_t(b),3.5,57,0.80))
    tuba.append(N(bar_t(b),3.8,38,0.75)); tuba.append(N(bar_t(b),3.8,26,0.70))
# Tuba continuous pedal 16-39, velocity arc (smooth LFE, no one-bar spikes)
for b in range(16,40):
    if b in (16,24,32): continue
    _tv=0.45+0.30*min(1.0,max(0.0,(b-16)/8.0)) if b<24 else (0.75 if b<32 else 0.60)
    tuba.append(N(bar_t(b),4.2,CH[PROG[b]][0],round(_tv,2)))
# Trombone marcato chase bars 32-39 beat1 short
for b in range(32,40):
    if b in (32,): continue
    root,tones=CH[PROG[b]]; tromb.append(N(bar_t(b),0.9,root+12,0.88)); tromb.append(N(bar_t(b),0.9,root+19,0.82))
# Trumpet fanfare finale bars 40-42
FANS=[[(0,1,74),(1,1,78),(2,2,81),(4,2,78),(6,2,74)],[(0.5,1,73),(1.5,1,76),(3,1.5,78),(5,1,76),(6.5,1.5,73)]]
for bi,b in enumerate([40,41]):
    for t,d,p in FANS[bi]: trump.append(N(bar_t(b)+t,d,p,0.88))
# Timpani bar starts bars 12-42 root/fifth, chase beat3 too
for b in range(12,43):
    root,tones=CH[PROG[b]]
    for _beat in range(4):
        timp.append(N(bar_t(b)+_beat,0.9,root+12 if _beat%2==0 else root+19,0.72+0.05*((b*3+_beat)%4)))
# Taiko beat1 bars 12-42, beat3 in chase
for b in range(12,43):
    if b%16==15: continue
    for _beat in range(4):
        taiko.append(N(bar_t(b)+_beat,0.9,60,0.70+0.04*((b*3+_beat)%4)))
    if b%4==3: taiko.append(N(bar_t(b)+3,0.8,67,0.70))
# Final hit bar43 beat1, then last D chord bar43 beat3? bar index 43 is last bar (beats 172-176)
pass # final hit covered by braam/full orchestra; orchestra_hit sample drifts DC
# Last chord horns/strings/choir/piano bar43 beat2 (after hit decay) long
for tr,p in [(horns,62),(strings,74),(choir,74),(piano,62)]:
    tr.append(N(bar_t(43)+2,1.8,p,0.80))
# silence before chase: ensure no notes at bar31 beat2-4 except bass/piano pad? remove celli already, keep others (they are pads, acceptable) - dynamics dip
score={
 "title":"Amazon Dinosaur - Giants Walking","bpm":BPM,"ts":[4,4],"seed":2027,"humanize":"natural",
 "key":"D","mode":"major","space":"amazon_dinosaur_room","mix_preset":"amazon_dinosaur_mix",
 "dynamics":[[0,0.40],[32,0.55],[64,0.70],[85,0.80],[96,0.70],[106,0.90],[128,1.0],[160,1.0],[176,0.95]],
 "ritard":0.0,"master":{"lufs":-14.0,"true_peak":-1.5,"tone":"neutral","fade_out":0.8},
 "output_targets":["stereo","immersive_7_1"],
 "piece_type":"cinematic","focus":"melody",
 "intent":{"emotions":["wonder","epic","majestic","triumphant"],"registers":["cinematic"],"scenes":["establish","build","arrival"],"tensions":["ostinato","silence_before","rising_line"],"avoid":["joyful","playful"]},
 "mix_intent":{"hero":"dino_horns","support":["dino_strings","dino_celli","dino_choir"],"leave_free_hz":[300,3500]},
 "plan":{"sections":[
   {"name":"first sight","start_bar":1,"end_bar":12,"energy":0.25,"start_s":0.0,"end_s":32.0},
   {"name":"herd rises","start_bar":13,"end_bar":24,"energy":0.55,"start_s":32.0,"end_s":64.0},
   {"name":"predator dread","start_bar":25,"end_bar":32,"energy":0.70,"start_s":64.0,"end_s":85.3},
   {"name":"chase","start_bar":33,"end_bar":40,"energy":0.90,"start_s":85.3,"end_s":106.7},
   {"name":"awe finale","start_bar":41,"end_bar":44,"energy":1.0,"start_s":106.7,"end_s":117.3}],
  "ending":{"fade_out":0.8}},
 "tracks":[
  {"name":"horns_theme","instrument":"dino_horns","role":"melody","notes":horns},
  {"name":"strings_pad","instrument":"dino_strings","role":"pad","notes":strings},
  {"name":"violas_counter","instrument":"dino_violas","role":"pad","notes":violas},
  {"name":"celli_ostinato","instrument":"dino_celli","role":"ostinato","notes":celli},
  {"name":"basses_pedal","instrument":"dino_basses","role":"bass","notes":basses},
  {"name":"trombones_braam","instrument":"dino_trombones","role":"chord","notes":tromb},
  {"name":"tuba_braam","instrument":"dino_tuba","role":"bass","notes":tuba},
  {"name":"trumpets_fanfare","instrument":"dino_trumpets","role":"chord","notes":trump},
  {"name":"timpani","instrument":"dino_timpani","role":"drum","notes":timp},
  {"name":"taiko","instrument":"dino_taiko","role":"drum","notes":taiko},
  {"name":"choir_pad","instrument":"dino_choir","role":"pad","notes":choir},
  {"name":"tremolo_dread","instrument":"dino_tremolo","role":"ostinato","notes":trem},
  ],
 "duration_s":117.3}
path=os.path.join(P,"scores","main_score.json")
json.dump(score,open(path,"w"),indent=1)
print(f"wrote {path} tracks={len(score['tracks'])} notes={sum(len(t['notes']) for t in score['tracks'])}")
