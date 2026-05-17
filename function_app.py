"""Azure Functions entry point for the scheduled sorter."""

from __future__ import annotations

import logging
import os

import azure.functions as func

from auth import get_access_token
from graph_client import GraphClient
from run_logger import write_run_log_to_store
from state_store import BlobStateStore
from topic_memory import (
    load_topic_memory_from_text,
    save_topic_memory_to_text,
)
from cloud_runner import run_cloud_sorter


app = func.FunctionApp()


@app.function_name(name="scheduled_outlook_sort")
@app.timer_trigger(
    schedule="%OUTLOOK_SORTER_SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def scheduled_outlook_sort(timer: func.TimerRequest) -> None:
    del timer
    logging.info("Scheduled Outlook sorter run started.")

    store = BlobStateStore(
        os.environ["AzureWebJobsStorage"],
        os.environ["OUTLOOK_SORTER_STATE_CONTAINER"],
    )
    access_token = get_access_token(state_store=store, allow_interactive=False)
    result = run_cloud_sorter(
        GraphClient(access_token),
        store,
        load_topic_memory_from_text,
        save_topic_memory_to_text,
    )
    log_name = write_run_log_to_store(store, result["run_log"])
    logging.info(
        "Scheduled Outlook sorter run finished. moved=%s log=%s",
        len(result["moved_messages"]),
        log_name,
    )
