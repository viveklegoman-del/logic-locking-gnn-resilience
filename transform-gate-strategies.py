 '''Wire Insertion / Dummy Gates:
    Scatters fake key-input-driven gates throughout the ENTIRE circuit
    (not just near the real lock block), so the GNN can no longer use
    'gates near a KEYINPUT' as a structural signature for the lock block.'''

def apply_wire_insertion(input_path, output_path, insertion_rate=0.05, seed=42):
  rng = random.Random(seed)
    with open(input_path) as f:
        lines = f.readlines()
 
    existing_wires = []
    keyinputs = []
    for line in lines:
        s = line.strip()
        if s.upper().startswith('INPUT(') and 'KEYINPUT' not in s.upper():
            continue
        if 'KEYINPUT' in s.upper() and s.upper().startswith('INPUT('):
            name = s[s.find('(') + 1:s.find(')')]
            keyinputs.append(name)
        m = GATE_LINE.match(s)
        if m:
            existing_wires.append(m.group(1))
 
    out = list(lines)
    dummy_count = 0
    n_insert = max(1, int(len(existing_wires) * insertion_rate))
 
    for _ in range(n_insert):
        if not existing_wires or not keyinputs:
            break
        dummy_count += 1
        driver_wire = rng.choice(existing_wires)
        fake_key = rng.choice(keyinputs)
        gtype = rng.choice(['AND', 'OR', 'XOR', 'NAND', 'NOR'])
        dummy_name = f'dummy_wire_{dummy_count}'
        insert_line = f'{dummy_name} = {gtype}({driver_wire}, {fake_key})\n'
        # insert at a random position after the driver's definition
        insert_at = rng.randint(0, len(out))
        out.insert(insert_at, insert_line)
 
    with open(output_path, 'w') as f:
        f.writelines(out)
    return dummy_count
 
'''STRATEGY 2: Netlist Flattening And Re-synthesis
    Runs the locked circuit through Yosys to re-see the
    gate-level netlist while preserving function. This remaps
    NAND/NOR/XOR patterns and destroys the structural fingerprint
    GNNUnlock's GNN learns to recognize.'''

def apply_resynthesis(input_path, output_path, yosys_bin='yosys'):
    
    script_path = output_path + '.ys'
    yosys_script = f
read_verilog -sv {input_path}
synth -flatten
abc -g AND,OR,XOR,NAND,NOR,XNOR
opt_clean
write_verilog {output_path}

    with open(script_path, 'w') as f:
        f.write(yosys_script)
 
    result = subprocess.run(
        [yosys_bin, '-s', script_path],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"⚠ Yosys re-synthesis failed for {input_path}")
        print(result.stderr[-500:])
        shutil.copy(input_path, output_path)  
    return result.returncode == 0

    
 '''Gate Camouflaging (structural)
    Decomposes XOR/XNOR gates — the strongest structural signature of
    the lock block (see Exp1-3 tables: XOR/XNOR had ~0.99 lock score) —
    into AND/OR/NOT equivalents so they blend in with ordinary gates
    used everywhere else in the circuit.'''

def apply_gate_camouflage(input_path, output_path):

    with open(input_path) as f:
        lines = f.readlines()
 
    out = []
    cam_count = 0
    for line in lines:
        s = line.strip()
        m = GATE_LINE.match(s)
        if m and m.group(2).upper() in ('XOR', 'XNOR'):
            out_wire, gtype, in_str = m.groups()
            in_wires = [w.strip() for w in in_str.split(',')]
            if len(in_wires) == 2:
                a, b = in_wires
                cam_count += 1
                na, nb = f'cam_not_{cam_count}_a', f'cam_not_{cam_count}_b'
                t1, t2 = f'cam_and_{cam_count}_1', f'cam_and_{cam_count}_2'
                out.append(f'{na} = NOT({a})\n')
                out.append(f'{nb} = NOT({b})\n')
                out.append(f'{t1} = AND({a}, {nb})\n')
                out.append(f'{t2} = AND({na}, {b})\n')
                if gtype.upper() == 'XOR':
                    out.append(f'{out_wire} = OR({t1}, {t2})\n')
                else:  # XNOR Work happening now
                    nt1, nt2 = f'cam_not_{cam_count}_1', f'cam_not_{cam_count}_2'
                    out.append(f'{nt1} = NOT({t1})\n')
                    out.append(f'{nt2} = NOT({t2})\n')
                    out.append(f'{out_wire} = AND({nt1}, {nt2})\n')
                continue
        out.append(line)
 
    with open(output_path, 'w') as f:
        f.writelines(out)
    return cam_count

 '''Random Netlist Perturbation
    Sprinkles random dummy logic paths across the whole circuit that
    structurally mimic the lock block's gate patterns, so the GNN
    produces false positives elsewhere and can't isolate the real
    lock gates with confidence.'''

def apply_random_perturbation(input_path, output_path, num_dummy_gates=50, seed=42):
   
    rng = random.Random(seed)
    with open(input_path) as f:
        lines = f.readlines()
 
    existing_wires = []
    for line in lines:
        m = GATE_LINE.match(line.strip())
        if m:
            existing_wires.append(m.group(1))
 
    out = list(lines)
    added = 0
    for i in range(num_dummy_gates):
        if len(existing_wires) < 2:
            break
        a, b = rng.sample(existing_wires, 2)
        gtype = rng.choice(['AND', 'OR', 'NAND', 'NOR', 'XOR', 'NOT'])
        dummy_name = f'rand_dummy_{i}'
        if gtype == 'NOT':
            line_new = f'{dummy_name} = NOT({a})\n'
        else:
            line_new = f'{dummy_name} = {gtype}({a}, {b})\n'
        insert_at = rng.randint(0, len(out))
        out.insert(insert_at, line_new)
        existing_wires.append(dummy_name)
        added += 1
 
    with open(output_path, 'w') as f:
        f.writelines(out)
    return added
