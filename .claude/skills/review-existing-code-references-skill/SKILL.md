---
name: review-existing-code-references-skill
description: Checks existing code references before starting new tasks to avoid duplication and ensure consistency. Also provides functionality to update the reference list.
---

# Review Existing Code References

This skill helps you leverage existing code and tests by checking a central reference file before starting new work. It also allows you to update this reference file when you create new reusable code.

## When to Use

- **Before writing new code**: To check if similar functionality, tests, or scripts already exist.
- **After creating new code**: To register new reusable scripts, tests, or utilities in the reference file.
- **When exploring the codebase**: To get a high-level overview of available tools and scripts.

## Instructions

### 1. Check Existing References

Before starting a task that involves writing new scripts, tests, or utilities:

1.  **Read the Reference File**:
    Read the file `c:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\.claude\skills\review-existing-code-references-skill\existing-code-for-reference.md`.

2.  **Search for Relevance**:
    Scan the `Function Type` and `Description` columns for keywords related to your current task.
    -   If you find relevant code, read that file to understand how it works and if it can be reused or adapted.
    -   If you find a similar test, check if it covers your test case.

3.  **Verify**:
    If you find a potential match, verify if it is still up-to-date and functional.

### 2. Update Reference File

After creating a new script, test, or utility that should be preserved for future reference:

1.  **Determine the Next ID**:
    Read the last entry in `existing-code-for-reference.md` to find the next available `code_XXXX` number.

2.  **Format the Entry**:
    Prepare a new table row with the following format:
    `| code_XXXX | function-type | description | [path/to/file](path/to/file) |`

    -   **code_XXXX**: The next sequential ID.
    -   **function-type**: A short category (e.g., `api-test`, `ui-testing`, `env-utils`).
    -   **description**: A concise description of what the code does.
    -   **code_documents**: A markdown link to the file, using the workspace-relative path.

3.  **Append to File**:
    Add the new row to the end of the table in `existing-code-for-reference.md`.

## Reference File Location

`c:\Users\Chris\Desktop\app\CICD\HK-Garden-App\HK_Garden_App\.claude\skills\review-existing-code-references-skill\existing-code-for-reference.md`
