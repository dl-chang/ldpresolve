# LDPResolve Prototype

## Dependencies
1. dnsdist
2. python3 (with dnspython package)
3. pdns-recursor (as AltRR)

## HOWTO
Run commands below after setting the parameters.

```
bash dnsdist/run_dnsdist.sh
bash noisy_stub/run_noisy_stub.sh
bash pdns-recursor/run_local_recursive_resolver.sh
```
## PARAMETERS
see files to set parameters

`dnsdist/run_dnsdist.sh`:

* path to dnsdist.lua

`dnsdist/dnsdist.lua`:

* epsilon_1
* epsilon_2
* sensitive list
* primary resolver
* alternative resolver

`noisy-stub/run_noisy_stub.sh`:

* sensitive list
* primary resolver
