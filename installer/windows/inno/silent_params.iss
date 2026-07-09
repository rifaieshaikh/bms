; Silent install parameters: /SILENT /MONGO=local|remote /MONGO_URI=... /DB_NAME=...

function GetSilentMongoMode(Param: String): String;
begin
  Result := ExpandConstant('{param:MONGO|remote}');
end;

function GetSilentMongoUri: String;
begin
  Result := ExpandConstant('{param:MONGO_URI|mongodb://localhost:27017}');
end;

function GetSilentDbName: String;
begin
  Result := ExpandConstant('{param:DB_NAME|zahcci_customization}');
end;

function IsSilentInstall: Boolean;
begin
  Result := (CompareText(ExpandConstant('{param:MONGO}'), '') <> 0) or WizardSilent;
end;
