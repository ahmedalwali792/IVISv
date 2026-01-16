import os

def fix_ingestion():
    path = "ingestion/main.py"
    with open(path, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    # Ingestion needs indentation for loop body lines
    # Loop body starts roughly after "while runtime.should_continue():" and "try:"
    # In my last view, "try:" was line 227 (0-indexed 226). 
    # But I might have file version from disk which has line numbers? No I read raw.
    
    # Logic:
    # 1. Ensure "try:" (4 spaces) opens the block.
    # 2. Ensure "while" (8 spaces) is inside.
    # 3. Ensure "try:" (12 spaces) is inside while.
    # 4. Indent everything from there until "except FatalError" (which should be 12 spaces).
    
    # Actually, simpler: just read the file, identify the range, and indent.
    # Range: 228 (1-based) to 356 (1-based).
    # "state.touch_loop()" is start.
    # "metrics.adaptive_fps_current.set" is end.
    
    in_loop_body = False
    in_except_block = False
    
    for i, line in enumerate(lines):
        if "state.touch_loop()" in line and "try:" not in line:
            in_loop_body = True
        
        if "except FatalError as e:" in line:
            in_loop_body = False
            in_except_block = True
            
        if "finally:" in line and "logger.info" not in line: # Main finally
            in_except_block = False

        # Indent inner body to 16 spaces (currently 12)
        if in_loop_body:
            # Check current indent
            stripped = line.lstrip()
            if stripped:
                current_indent = len(line) - len(stripped)
                if current_indent == 12:
                    new_lines.append("    " + line)
                else:
                    new_lines.append(line) # Assume already correct or empty
            else:
                new_lines.append(line)
        # Indent inner excepts to 12 spaces (currently 8)
        elif in_except_block:
             stripped = line.lstrip()
             if stripped:
                current_indent = len(line) - len(stripped)
                if current_indent == 8:
                    new_lines.append("    " + line)
                else:
                     new_lines.append(line)
             else:
                new_lines.append(line)
        else:
            # Fix the outer structure
            if "while runtime.should_continue():" in line:
                # Ensure while is at 8 spaces
                new_lines.append("        while runtime.should_continue():\n")
            elif "try:" in line and "import" not in line:
                # Identify which try
                # If it's the one before while...
                if i < 227 and i > 220: # Rough check
                    new_lines.append("    try:\n")
                # If it's the one inside while...
                elif i > 225 and i < 230:
                     new_lines.append("            try:\n")
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

    with open(path, "w") as f:
        f.writelines(new_lines)
    print(f"Fixed {path}")

def fix_detection():
    path = "detection/main.py"
    with open(path, "r") as f:
        lines = f.readlines()
        
    new_lines = []
    # Detection: Revert "for" to "try...for" and add valid close
    # Current state: "        for frame_contract in consumer:" (8 spaces)
    # Body: 16 spaces (mostly)
    # We want:
    # "        try:"
    # "            for..." (12 spaces)
    # Body (16 spaces) - this matches!
    # Ending: add "        finally: pass" before "    except FatalError:"
    
    for i, line in enumerate(lines):
        if "for frame_contract in consumer:" in line:
            new_lines.append("        try:\n")
            new_lines.append("            for frame_contract in consumer:\n")
        elif "except FatalError:" in line and "as e" not in line:
            # This is the outer except (line 261 approx)
            # We need to close the inner try (8 spaces) before this (4 spaces)
            new_lines.append("        finally:\n")
            new_lines.append("            pass\n")
            new_lines.append(line)
        else:
            new_lines.append(line)
            
    with open(path, "w") as f:
        f.writelines(new_lines)
    print(f"Fixed {path}")

if __name__ == "__main__":
    fix_ingestion()
    fix_detection()
