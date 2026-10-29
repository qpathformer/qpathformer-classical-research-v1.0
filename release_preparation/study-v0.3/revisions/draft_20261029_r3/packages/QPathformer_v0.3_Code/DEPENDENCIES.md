# Dependencies

The recorded numeric environment used Python 3.12.14, NumPy 2.5.4, SciPy 1.18.1, Qiskit 2.6.0 and Qiskit Aer 0.17.2. Exact saved binomial/bootstrap count replay requires the registered NumPy version; bounded startup does not perform that replay. 

[Dependency inventory](DEPENDENCY_INVENTORY.json) maps imports and observed locks. Full observed locks can include unrelated packages and are not minimum dependency specifications. Third-party dependencies retain their separate terms; no dependency binaries or environments are included. No hardware minimum is inferred from archive size or startup success.

The direct import inventory includes all 47 retained scientific Python files and both package helpers. Helper imports use the standard library and local verifier; they add no third-party dependency. A bounded startup receipt records the actual imported NumPy version separately from the historical environment.
