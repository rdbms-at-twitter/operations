aws rds describe-db-engine-versions --engine  aurora-postgresql --query 'DBEngineVersions[].EngineVersion' --output table
