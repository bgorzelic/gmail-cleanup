---
name: Bug report
about: Something gmail-cleanup did wrong or unexpectedly
title: "[bug] "
labels: bug
---

**What you ran**

```
# Full command line, including flags
gmail-cleanup ...
```

**What you expected**

<!-- One sentence -->

**What actually happened**

<!-- Output, error message, or behavior. Include --dry-run output if relevant. -->

**Reproducibility**

- [ ] Reproduces every time
- [ ] Reproduces sometimes
- [ ] Happened once

**Environment**

- OS: <!-- e.g. macOS 14.5, Ubuntu 22.04 -->
- Python: <!-- output of `python3 --version` -->
- gmail-cleanup version: <!-- output of `pip show gmail-cleanup | grep Version` -->
- Gmail account type: <!-- personal, workspace, work — but don't include the email -->

**Safety-critical?**

If this involves accidental loss of mail, a KEEP-list bypass, or unsubscribing from something it shouldn't have:
- [ ] Yes — this is safety-critical (we'll patch fast)
- [ ] No — feature/UX issue
