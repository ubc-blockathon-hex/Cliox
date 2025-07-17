# test_rag.py
from pathlib import Path
from types import SimpleNamespace
from algorithm import Algorithm
import os

# DEBUG WHERE AM I??
print("Current working directory:", os.getcwd())

# 1. Point to your sample file
files = SimpleNamespace(files=[SimpleNamespace(input_files=[Path("./src/implementation/enron-sample-data.json")])])

# 2. Mock JobDetails with parameters.query
job_details = SimpleNamespace(files=files, parameters={"query": "What covers most of Earth's surface?"})

# 3. Run it
alg = Algorithm(job_details).run()

# 4. Save & print out
out_dir = Path("out")
out_dir.mkdir(exist_ok=True)
alg.save_result(out_dir)

print("Result:", (out_dir / "result.json").read_text(encoding="utf-8"))
