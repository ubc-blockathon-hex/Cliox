from pathlib import Path
from types import SimpleNamespace
from algorithm import Algorithm
import os,logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# DEBUG WHERE AM I??
print("Current working directory:", os.getcwd())

# Sample data
files = SimpleNamespace(files=[SimpleNamespace(input_files=[Path("./src/implementation/enron-sample-data.json")])])

# Mock JobDetails
job_details = SimpleNamespace(files=files, parameters={"query": "What covers most of Earth's surface?"})

logger.info("Starting compute job")
alg = Algorithm(job_details).run()
logger.info("Saving compute job")
out_dir = Path("out")
logger.info(out_dir)
out_dir.mkdir(exist_ok=True)
alg.save_result(out_dir)

print("Result:", (out_dir / "result.json").read_text(encoding="utf-8"))
logger.info(out_dir)
