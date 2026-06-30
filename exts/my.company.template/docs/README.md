# My Company Template Extension

A minimal template extension for Isaac Sim 5.0.0 (Kit 107.3.1).

It opens a window with a button that increments a counter. Use it as a
starting point for your own tools.

## Structure

```
my.company.template/
├── config/
│   └── extension.toml      # Extension manifest
├── docs/
│   └── README.md
└── my/company/template/
    ├── __init__.py
    └── extension.py        # on_startup / on_shutdown lifecycle + UI
```
