// claudestate-go.go
//
// Lightweight Go companion for ClaudeState.
// Reads STATE.md and outputs a JSON summary — useful for Go-based
// build pipelines, Makefiles, or pre-commit hooks.
//
// Build:   go build -o claudestate-go ./claudestate-go.go
// Run:     ./claudestate-go [--path /your/project]
// Output:  JSON on stdout

package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// ── types ─────────────────────────────────────────────────────────────────────

type Task struct {
	Done bool   `json:"done"`
	Text string `json:"text"`
}

type StateSummary struct {
	ProjectRoot string    `json:"project_root"`
	StateFile   string    `json:"state_file"`
	TotalTasks  int       `json:"total_tasks"`
	DoneTasks   int       `json:"done_tasks"`
	PctDone     int       `json:"pct_done"`
	NextTask    string    `json:"next_task"`
	HasBlockers bool      `json:"has_blockers"`
	GeneratedAt time.Time `json:"generated_at"`
}

// ── task parser ───────────────────────────────────────────────────────────────

var taskRe = regexp.MustCompile(`^\s*-\s+\[( |x)\]\s+(.+)$`)

func parseTasks(content string) []Task {
	var tasks []Task
	scanner := bufio.NewScanner(strings.NewReader(content))
	for scanner.Scan() {
		line := scanner.Text()
		m := taskRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		tasks = append(tasks, Task{
			Done: strings.EqualFold(m[1], "x"),
			Text: strings.TrimSpace(m[2]),
		})
	}
	return tasks
}

func hasBlockers(content string) bool {
	inBlockers := false
	scanner := bufio.NewScanner(strings.NewReader(content))
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "## Blockers") {
			inBlockers = true
			continue
		}
		if inBlockers {
			if strings.HasPrefix(line, "## ") {
				break
			}
			trimmed := strings.TrimSpace(line)
			if trimmed != "" && !strings.HasPrefix(trimmed, "*(none)") {
				return true
			}
		}
	}
	return false
}

// ── find STATE.md ─────────────────────────────────────────────────────────────

func findState(start string) (string, error) {
	dir := start
	for {
		candidate := filepath.Join(dir, "STATE.md")
		if _, err := os.Stat(candidate); err == nil {
			return candidate, nil
		}
		// stop at git root
		if _, err := os.Stat(filepath.Join(dir, ".git")); err == nil {
			break
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "", fmt.Errorf("STATE.md not found (run: claudestate init)")
}

// ── main ──────────────────────────────────────────────────────────────────────

func main() {
	projectPath := flag.String("path", "", "Project root (default: cwd)")
	prettyFlag  := flag.Bool("pretty", false, "Pretty-print JSON output")
	flag.Parse()

	root := *projectPath
	if root == "" {
		var err error
		root, err = os.Getwd()
		if err != nil {
			fmt.Fprintf(os.Stderr, "error: %v\n", err)
			os.Exit(1)
		}
	}

	statePath, err := findState(root)
	if err != nil {
		fmt.Fprintf(os.Stderr, "claudestate: %v\n", err)
		os.Exit(1)
	}

	data, err := os.ReadFile(statePath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot read %s: %v\n", statePath, err)
		os.Exit(1)
	}
	content := string(data)

	tasks    := parseTasks(content)
	done     := 0
	nextTask := "All tasks complete!"
	for _, t := range tasks {
		if t.Done {
			done++
		}
	}
	for _, t := range tasks {
		if !t.Done {
			nextTask = t.Text
			break
		}
	}
	pct := 0
	if len(tasks) > 0 {
		pct = done * 100 / len(tasks)
	}

	summary := StateSummary{
		ProjectRoot: filepath.Dir(statePath),
		StateFile:   statePath,
		TotalTasks:  len(tasks),
		DoneTasks:   done,
		PctDone:     pct,
		NextTask:    nextTask,
		HasBlockers: hasBlockers(content),
		GeneratedAt: time.Now().UTC(),
	}

	var out []byte
	if *prettyFlag {
		out, _ = json.MarshalIndent(summary, "", "  ")
	} else {
		out, _ = json.Marshal(summary)
	}
	fmt.Println(string(out))
}
