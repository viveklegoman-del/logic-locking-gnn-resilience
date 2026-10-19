print("Test Time")
os.makedirs(EXP2_CIRCUIT_DIR, exist_ok=True)
for f in os.listdir(EXP2_CIRCUIT_DIR):
    os.remove(os.path.join(EXP2_CIRCUIT_DIR, f))

for fname in os.listdir(CIRCUIT_SRC):
    if not fname.endswith('.bench'):
        continue
    src = os.path.join(CIRCUIT_SRC, fname)
    dst = os.path.join(EXP2_CIRCUIT_DIR, fname)

    if fname.startswith('Test_') and not fname.startswith('Test_Validate'):
        if 'c7552' in fname and 'k_32' in fname:
            apply_demorgan(src, dst)   # The actual test, in this case benchmark circuit c7552, and testing DeMorgan's law
        continue
    if fname.startswith('Train_') and any(c in fname for c in ['c2670','c5315']):
        shutil.copy(src, dst)          # ← RAW train without any cricuit modifications
        continue
    if (fname.startswith('Validate_') or fname.startswith('Test_Validate_')) and 'c3540' in fname:
        shutil.copy(src, dst)          # ← RAW validate without any circuit modifications
        continue

files = os.listdir(EXP2_CIRCUIT_DIR)
test_f = [f for f in files if f.startswith('Test_') and not f.startswith('Test_Validate')]
train_f = [f for f in files if f.startswith('Train_')]
val_f = [f for f in files if f.startswith('Validate_') or f.startswith('Test_Validate')]
print(f"Test ({len(test_f)}): {test_f}")
print(f"Train ({len(train_f)} files)")
print(f"Val ({len(val_f)} files)")
