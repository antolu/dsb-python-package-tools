Package usage
=============

The DSB devtools package is a convenience package for BE-CSS-DSB section to consolidate Python devops.

# Package usage

The main use of the package is the `dsb-pkginit` entrypoint, which is equivalent to `python -m dsb_devtools.pkginit`.

The `dsb-pkginit` command is used to initialize a new Python package.
It creates a new directory with the package name, and initializes a new git repository in it.

Run `dsb-pkginit` for an interactive package setup process.


## Run on the TN

dsb-pkginit is also deployed on the TN Acc-Py distribution, runnable as

```bash
acc-py app run dsb-pkginit
```
