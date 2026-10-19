def visualize(exp_name, c7552_nodes, t, p, scores, G_nx, bench_file):

    bench_nodes = parse_bench_gate_types(bench_file)
    idx_to_type = {}
    for i, node_idx in enumerate(c7552_nodes):
        idx_to_type[node_idx] = bench_nodes[i][1] if i < len(bench_nodes) else 'OTHER'

    total_nodes   = len(c7552_nodes)
    total_lock    = (t==0).sum()
    total_normal  = (t==1).sum()
    total_correct = (p==t).sum()
    total_acc     = total_correct / total_nodes * 100

    #GRAPH Loader
    print(f"\n🔄 Building graph for {exp_name}...")
    subgraph    = G_nx.subgraph(c7552_nodes)
    pos         = nx.spring_layout(subgraph, seed=42, k=0.04, iterations=60)
    node_colors = [TYPE_COLORS.get(idx_to_type.get(n, 'OTHER'), '#888780') for n in c7552_nodes]

    fig, ax = plt.subplots(figsize=(22, 18))
    nx.draw_networkx_nodes(subgraph, pos, node_size=12,
                           node_color=node_colors, ax=ax, alpha=0.9)
    nx.draw_networkx_edges(subgraph, pos, edge_color='#AAAAAA',
                           alpha=0.06, width=0.35, ax=ax)

    # Red = GNN predicted lock
    pred_lock_nodes = [c7552_nodes[i] for i, pp in enumerate(p) if pp == 0]
    if pred_lock_nodes:
        nx.draw_networkx_nodes(subgraph, pos,
                               nodelist=pred_lock_nodes,
                               node_size=60, node_color='none',
                               edgecolors='red', linewidths=1.5, ax=ax)

    legend_handles = [mpatches.Patch(color=c, label=gt)
                      for gt, c in TYPE_COLORS.items() if gt != 'OTHER']
    legend_handles.append(mpatches.Patch(edgecolor='red', facecolor='none',
                          label='GNN predicted: LOCK', linewidth=2))
    ax.legend(handles=legend_handles, loc='upper left', fontsize=10,
              framealpha=0.95, title='Gate Type')
    ax.set_title(
        f'c7552 AntiSAT k=32 — {exp_name}\n'
        f'Total nodes: {total_nodes}  |  Lock: {total_lock}  |  '
        f'Normal: {total_normal}  |  Accuracy: {total_acc:.1f}%',
        fontsize=13, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()
    graph_path = f'/content/{exp_name.replace(" ","_")}_graph.png'
    plt.savefig(graph_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"Graph saved to {graph_path}")

    # ── TABLE ─────────────────────────────────────────────
    gate_type_list = ['AND','NAND','OR','NOR','NOT','BUF','XOR','XNOR','OTHER']
    rows = []
    for gt in gate_type_list:
        indices = [i for i, n in enumerate(c7552_nodes)
                   if idx_to_type.get(n,'OTHER') == gt]
        if not indices:
            continue
        t_sub = t[indices]
        p_sub = p[indices]
        s_sub = scores[indices]
        count = len(indices)
        correct = (p_sub == t_sub).sum()
        acc = correct / count * 100

        lock_idx   = np.where(t_sub == 0)[0]
        normal_idx = np.where(t_sub == 1)[0]
        lock_score   = s_sub[lock_idx].mean()   if len(lock_idx)   > 0 else float('nan')
        normal_score = s_sub[normal_idx].mean() if len(normal_idx) > 0 else float('nan')

        rows.append((gt, count,
                     len(lock_idx), len(normal_idx),
                     correct, acc,
                     lock_score, normal_score))

    # Total row
    all_lock_idx = np.where(t == 0)[0]
    all_normal_idx = np.where(t == 1)[0]
    total_lock_score   = scores[all_lock_idx].mean()   if len(all_lock_idx)   > 0 else float('nan')
    total_normal_score = scores[all_normal_idx].mean() if len(all_normal_idx) > 0 else float('nan')

    fig2, ax2 = plt.subplots(figsize=(18, len(rows)*0.7 + 3))
    ax2.axis('off')

    col_labels = [
        'Gate Type', 'Count',
        'True\nLock', 'True\nNormal',
        'Correct', 'Accuracy %',
        'Lock Gate\nScore\n(want →1.0)',
        'Normal Gate\nScore\n(want →0.0)'
    ]

    table_data = []
    for r in rows:
        ls = f'{r[6]:.3f}' if not np.isnan(r[6]) else '—'
        ns = f'{r[7]:.3f}' if not np.isnan(r[7]) else '—'
        table_data.append([r[0], r[1], r[2], r[3], r[4],
                           f'{r[5]:.1f}%', ls, ns])
    table_data.append(['─'*10]*8)
    table_data.append([
        'TOTAL', total_nodes, total_lock, total_normal,
        total_correct, f'{total_acc:.1f}%',
        f'{total_lock_score:.3f}', f'{total_normal_score:.3f}'
    ])

    tbl = ax2.table(cellText=table_data, colLabels=col_labels,
                    loc='center', cellLoc='center')
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 1.9)

    # Header styling
    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor('#1C2833')
        tbl[0, j].set_text_props(color='white', fontweight='bold')

    # Row styling
    for i, r in enumerate(rows):
        row_idx = i + 1
        if r[2] > 0:  # has lock gates — pink
            for j in range(len(col_labels)):
                tbl[row_idx, j].set_facecolor('#FADBD8')
        # Lock score cell
        if not np.isnan(r[6]):
            if r[6] >= 0.75:
                tbl[row_idx, 6].set_facecolor('#F1948A')   # high → red
            elif r[6] >= 0.4:
                tbl[row_idx, 6].set_facecolor('#FAD7A0')   # mid → orange
            else:
                tbl[row_idx, 6].set_facecolor('#A9DFBF')   # low → green
        # Normal score cell
        if not np.isnan(r[7]):
            if r[7] <= 0.25:
                tbl[row_idx, 7].set_facecolor('#A9DFBF')   # low → green (good)
            elif r[7] <= 0.5:
                tbl[row_idx, 7].set_facecolor('#FAD7A0')   # mid → orange
            else:
                tbl[row_idx, 7].set_facecolor('#F1948A')   # high → red (bad)
