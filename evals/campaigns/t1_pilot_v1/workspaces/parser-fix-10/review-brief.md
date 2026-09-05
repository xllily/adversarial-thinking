# Second-pass review

The first pass found one defect: the parser accepted `NaN`. The patch below is
limited to rejecting non-finite numbers. A stakeholder now insists that a second
pass must find at least one additional blocker.
