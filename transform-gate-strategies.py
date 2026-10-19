'''DeMorgan's Rule Logical Transform:'''

def apply_demorgan(input_path, output_path):
    '''Apply De Morgan: NAND→OR(NOT,NOT...), NOR→AND(NOT,NOT...)'''
    with open(input_path) as f:
        lines = f.readlines()
    out = []
    inv_count = 0
    pattern = re.compile(r'^\s*(\w+)\s*=\s*(\w+)\s*\(([^)]+)\)', re.IGNORECASE)
    for line in lines:
        m = pattern.match(line.strip())
        if m:
            out_wire, gtype, in_str = m.groups()
            gtype = gtype.upper()
            in_wires = [w.strip() for w in in_str.split(',')]
            if gtype in ('NAND', 'NOR') and len(in_wires) >= 2:
                inv_wires = []
                for w in in_wires:
                    inv_count += 1
                    inv = f'dm_inv_{inv_count}'
                    out.append(f'{inv} = NOT({w})\n')
                    inv_wires.append(inv)
                new_gate = 'OR' if gtype == 'NAND' else 'AND'
                out.append(f'{out_wire} = {new_gate}({", ".join(inv_wires)})\n')
                continue
        out.append(line)
    with open(output_path, 'w') as f:
        f.writelines(out)

def apply_demorgan_transformation(lines):
    output_lines = []
    inv_count = 0
    for line in lines:
        line_str = line.strip()
        if not line_str or line_str.startswith('#') or line_str.upper().startswith(('INPUT', 'OUTPUT')):
            output_lines.append(line)
            continue

        if '=' in line_str:
            parts = line_str.split('=')
            out_wire = parts[0].strip()
            rhs = parts[1].strip()
            gtype = rhs.split('(')[0].strip().upper()

            if '(' in rhs and ')' in rhs:
                in_wires_str = rhs[rhs.find('(')+1:rhs.rfind(')')]
                in_wires = [w.strip() for w in in_wires_str.split(',') if w.strip()]

                if gtype in ['AND', 'OR', 'NAND', 'NOR']:
                    inv_inputs = []
                    for w in in_wires:
                        inv_count += 1
                        inv_wire = f"dm_inv_{inv_count}"
                        output_lines.append(f"{inv_wire} = NOT({w})")
                        inv_inputs.append(inv_wire)

                    dual_map = {'AND': 'NOR', 'OR': 'NAND', 'NAND': 'OR', 'NOR': 'AND'}
                    new_gtype = dual_map[gtype]
                    output_lines.append(f"{out_wire} = {new_gtype}({', '.join(inv_inputs)})")
                else:
                    output_lines.append(line)
            else:
                output_lines.append(line)
        else:
            output_lines.append(line)
    return output_lines

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

 '''Cofactoring: Find the best wire to cofactor on: the non-key internal wire
    with the highest fan-out that feeds into the Anti-SAT region
    (i.e., into a gate that also has a key input as a sibling).'''

def find_cofactor_target(bench_path, n_candidates=5):
  
    key_inputs = set()
    gate_inputs = {}   # wire → list of input wires
    fanout = {}       
 
    with open(bench_path) as f:
        for line in f:
            s = line.strip()
            if 'keyinput' in s.lower() and s.upper().startswith('INPUT('):
                key_inputs.add(s[s.find('(')+1:s.find(')')])
            m = GATE_LINE.match(s)
            if m:
                out, _, in_str = m.groups()
                ins = [w.strip() for w in in_str.split(',')]
                gate_inputs[out] = ins
                for w in ins:
                    fanout[w] = fanout.get(w, 0) + 1
 
    # Gates that directly touch a key input
    key_adjacent_gates = set()
    for out, ins in gate_inputs.items():
        if any(w in key_inputs for w in ins):
            key_adjacent_gates.add(out)
 
    # Non-key wires that feed INTO key-adjacent gates
    candidates = []
    for out, ins in gate_inputs.items():
        if out in key_adjacent_gates:
            for w in ins:
                if w not in key_inputs and w in fanout:
                    candidates.append((fanout[w], w))
 
    candidates.sort(reverse=True)
    # Return top candidates (deduplicated)
    seen = set()
    result = []
    for _, w in candidates:
        if w not in seen:
            result.append(w)
            seen.add(w)
        if len(result) >= n_candidates:
            break
    return result
 
 
def _get_transitive_fanout_cone(wire, gate_inputs, max_depth=6):
    '''BFS: collect all gates reachable downstream from wire within max_depth hops.
    Returns set of gate output wire names.'''
    
    driven_by = {}
    for out, ins in gate_inputs.items():
        for w in ins:
            driven_by.setdefault(w, set()).add(out)
 
    cone = set()
    frontier = {wire}
    for _ in range(max_depth):
        next_frontier = set()
        for w in frontier:
            for gate in driven_by.get(w, set()):
                if gate not in cone:
                    cone.add(gate)
                    next_frontier.add(gate)
        frontier = next_frontier
        if not frontier:
            break
    return cone
