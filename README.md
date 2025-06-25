# FastMCP Rust Documentation Server

## Installation

To set up the project, follow these steps:

1. **Clone the repository**:

   ```bash
   git clone https://github.com/ai-tools-all/rust_docs_mcp.git  
   cd rust_docs_mcp
   uv sync
   ```


2. **Run the server**:

   ```bash
   uv run both_stdio_server.py sse
   ```

This will install all necessary dependencies for the project.


This project implements a FastMCP server designed to manage and provide access to Rust crate documentation from [docs.rs](https://docs.rs/). It offers functionalities to parse `Cargo.lock` files, fetch documentation, cache it locally, and serve it via the FastMCP protocol.

## Features

- **Dependency Parsing**: Reads `Cargo.lock` files to identify Rust project dependencies and their versions.
- **Documentation Scraping**: Fetches comprehensive documentation for specified crates and versions directly from `docs.rs`.
- **Local Caching**: Stores scraped documentation as Markdown files locally to enable offline access and faster retrieval.
- **Structured Logging**: Implements structured JSON logging for better observability and debugging.
- **HTML to Markdown Conversion**: Converts HTML documentation from `docs.rs` into a readable Markdown format.

## Project Structure

The core logic of the server is organized within the `src/` directory:

- `src/core.py`: Contains the main business logic, including functions for reading `Cargo.lock`, fetching and saving documentation, and listing cached documents. These functions are designed to be independent of the FastMCP context for reusability and testability.
- `src/html_to_markdown.py`: Provides utilities for converting HTML content (scraped from `docs.rs`) into Markdown format. It leverages the `html2markdown` command-line tool.
- `src/logger.py`: Configures the application's logging system, providing structured JSON logs with file rotation.
- `src/parser.py`: Houses the `CargoLockParser` class, responsible for parsing `Cargo.lock` files to extract dependency names and versions.
- `src/scraper.py`: Implements the `DocsRsScraper` class, which handles the web scraping of `docs.rs`, parsing HTML content using `BeautifulSoup`, and managing the caching of documentation.

## Usage

### HTML to Markdown Conversion

To convert HTML files to Markdown using `html_to_markdown.py`, you can run:

```bash
uv run src/html_to_markdown.py
```

### Running the Server

The server can be run in different transport modes:

- **STDIO (Default)**:

  ```bash
  uv run both_stdio_server.py
  ```

- **SSE (Server-Sent Events)**:

  ```bash
  uv run both_stdio_server.py sse
  ```

- **HTTP**:

  ```bash
  uv run both_stdio_server.py http
  ```

These commands assume you have `uv` installed and are running them from the project's root directory.

### Prerequisites

- `uv`: A fast Python package installer and resolver. If you don't have it, you can install it via `pip install uv`.
- `html2markdown`: A command-line tool for converting HTML to Markdown. You might need to install it separately (e.g., `pip install html2markdown`).