## Pioreactor plugin template

[Instructions for making plugin packages [here](https://docs.pioreactor.com/developer-guide/plugin-as-python-package).]

Explain what the plugin does here

## Installation

Install from the Pioreactor plugins web interface or the command line:

```
pio install-plugin [NAME OF PLUGIN HERE - remember to use hyphens (-) to separate words]    # to install directly on the Pioreactor

# OR, on the leader's command line:

pios install-plugin [NAME OF PLUGIN HERE - remember to use hyphens (-) to separate words] # to install on all Pioreactors in a cluster
```

Or install through the web interface (_Plugins_ tab). This will install the plugin on all Pioreactors within the cluster.

[You might want to put extra instructions here for editing config files etc e.g for the relay plugin:]

```
[PWM]
<the PWM channel you pick>=relay

[relay.config]
hz=100
post_delay_duration=0.2
pre_delay_duration=1.5
enable_dodging_od=1
```

## Usage

#### Through the command line:
```
pio run [PYTHON FILE NAME]
```

#### Through the UI:

Under _Manage_, there will be a new _Activities_ option called _[PYTHON FILE NAME]_. Editable settings include [ADD EDITABLE SETTINGS HERE] 

## Plugin documentation

Documentation for plugins can be found on the [Pioreactor docs](https://docs.pioreactor.com/developer-guide/intro-plugins).
