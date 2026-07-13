from temporalio import activity


@activity.defn
async def validate_asset(filename: str) -> str:
    print(f"Validating asset: {filename}")
    return f"{filename} validated"