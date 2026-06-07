import time

from celery_app import celery


@celery.task(bind=True)
def process_items_task(self, total_items):
    print(f"Task {self.request.id}: Starting to process {total_items} items.")
    processed_count = 0
    for i in range(total_items):
        # Simulate work for each item
        time.sleep(1)
        processed_count += 1
        message = f"Processed {processed_count} of {total_items} items."

        self.update_state(
            state="PROGRESS",
            meta={"current": processed_count, "total": total_items, "status": message},
        )
        print(f"Task {self.request.id}: {message}")

    final_message = f"Successfully processed all {total_items} items."
    print(f"Task {self.request.id}: {final_message}")
    return {
        "current": total_items,
        "total": total_items,
        "status": "Processing complete!",
        "result": final_message,  # You can return any serializable result
    }
