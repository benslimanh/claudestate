//! claudestate-rs
//!
//! Lightweight Rust library + binary that reads STATE.md and
//! outputs a structured summary. Use in Cargo build scripts,
//! pre-commit hooks, or CI pipelines.
//!
//! # Quick start
//! ```bash
//! cargo run -- --pretty
//! cargo run -- --path /your/project
//! ```

use std::env;
use std::fs;
use std::path::{Path, PathBuf};

use serde::Serialize;

// ── types ─────────────────────────────────────────────────────────────────────

#[derive(Debug, Serialize)]
struct Task {
    done: bool,
    text: String,
}

#[derive(Debug, Serialize)]
struct StateSummary {
    project_root: String,
    state_file:   String,
    total_tasks:  usize,
    done_tasks:   usize,
    pct_done:     usize,
    next_task:    String,
    has_blockers: bool,
}

// ── parser ────────────────────────────────────────────────────────────────────

fn parse_tasks(content: &str) -> Vec<Task> {
    content
        .lines()
        .filter_map(|line| {
            let trimmed = line.trim();
            if let Some(rest) = trimmed.strip_prefix("- [") {
                if let Some(after) = rest.strip_prefix("x] ").or_else(|| rest.strip_prefix("X] ")) {
                    return Some(Task { done: true, text: after.trim().to_owned() });
                }
                if let Some(after) = rest.strip_prefix(" ] ") {
                    return Some(Task { done: false, text: after.trim().to_owned() });
                }
            }
            None
        })
        .collect()
}

fn has_blockers(content: &str) -> bool {
    let mut in_blockers = false;
    for line in content.lines() {
        if line.starts_with("## Blockers") {
            in_blockers = true;
            continue;
        }
        if in_blockers {
            if line.starts_with("## ") {
                break;
            }
            let t = line.trim();
            if !t.is_empty() && !t.starts_with("*(none)") {
                return true;
            }
        }
    }
    false
}

// ── find STATE.md ─────────────────────────────────────────────────────────────

fn find_state(start: &Path) -> Option<PathBuf> {
    let mut dir = start.to_path_buf();
    loop {
        let candidate = dir.join("STATE.md");
        if candidate.exists() {
            return Some(candidate);
        }
        if dir.join(".git").exists() {
            break;
        }
        match dir.parent() {
            Some(p) if p != dir => dir = p.to_path_buf(),
            _ => break,
        }
    }
    None
}

// ── main ──────────────────────────────────────────────────────────────────────

fn main() {
    let args: Vec<String> = env::args().collect();
    let pretty = args.iter().any(|a| a == "--pretty");
    let path_arg = args.windows(2)
        .find(|w| w[0] == "--path")
        .map(|w| PathBuf::from(&w[1]));

    let root = path_arg.unwrap_or_else(|| env::current_dir().expect("cwd failed"));

    let state_path = match find_state(&root) {
        Some(p) => p,
        None => {
            eprintln!("claudestate: STATE.md not found. Run `claudestate init`.");
            std::process::exit(1);
        }
    };

    let content = fs::read_to_string(&state_path)
        .unwrap_or_else(|e| { eprintln!("Cannot read STATE.md: {e}"); std::process::exit(1); });

    let tasks = parse_tasks(&content);
    let done  = tasks.iter().filter(|t| t.done).count();
    let next  = tasks.iter()
        .find(|t| !t.done)
        .map(|t| t.text.clone())
        .unwrap_or_else(|| "All tasks complete!".to_owned());

    let pct = if tasks.is_empty() { 0 } else { done * 100 / tasks.len() };

    let summary = StateSummary {
        project_root: state_path.parent().unwrap().display().to_string(),
        state_file:   state_path.display().to_string(),
        total_tasks:  tasks.len(),
        done_tasks:   done,
        pct_done:     pct,
        next_task:    next,
        has_blockers: has_blockers(&content),
    };

    let output = if pretty {
        serde_json::to_string_pretty(&summary)
    } else {
        serde_json::to_string(&summary)
    }
    .expect("serialization failed");

    println!("{output}");
}
