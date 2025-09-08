# internet-measurement-network
The entire AIORI Internet Measurement Network - Redesigned

## Start Nats.io server with the command
```
$ nats-server -n newton -m 8222 -DVV
```

> [!NOTE]
> The `-m 8222` is necessary for the central server cluster to get information about connected agents 

> [!NOTE]
> Note: The `nats-server` will always be a cluster, and not single server as shown in the above command.

## Run the agent
```
python -m pip install requirements.txt
python agent start
```

> [!NOTE]
> Note: While running the above `python agent start` command, the working directory whould be the one with the `agent/` directory.
