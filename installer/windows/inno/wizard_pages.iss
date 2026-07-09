// MongoDB wizard custom pages for VayBooks-BMS installer

var
  MongoPage: TWizardPage;
  MongoRemoteRadio: TNewRadioButton;
  MongoLocalRadio: TNewRadioButton;
  MongoUriLabel: TNewStaticText;
  MongoUriEdit: TNewEdit;
  DbNameLabel: TNewStaticText;
  DbNameEdit: TNewEdit;

procedure InitializeMongoWizardPages;
var
  InfoText: TNewStaticText;
begin
  MongoPage := CreateCustomPage(
    wpSelectDir,
    'MongoDB Configuration',
    'Choose how VayBooks-BMS connects to MongoDB.'
  );

  InfoText := TNewStaticText.Create(MongoPage);
  InfoText.Parent := MongoPage.Surface;
  InfoText.Caption := 'Select an existing MongoDB (Atlas or remote) or install MongoDB locally.';
  InfoText.Left := 0;
  InfoText.Top := 0;
  InfoText.Width := MongoPage.SurfaceWidth;

  MongoRemoteRadio := TNewRadioButton.Create(MongoPage);
  MongoRemoteRadio.Parent := MongoPage.Surface;
  MongoRemoteRadio.Caption := 'Use existing MongoDB connection';
  MongoRemoteRadio.Left := 0;
  MongoRemoteRadio.Top := 40;
  MongoRemoteRadio.Width := MongoPage.SurfaceWidth;
  MongoRemoteRadio.Checked := True;

  MongoUriLabel := TNewStaticText.Create(MongoPage);
  MongoUriLabel.Parent := MongoPage.Surface;
  MongoUriLabel.Caption := 'Connection String:';
  MongoUriLabel.Left := 20;
  MongoUriLabel.Top := 70;

  MongoUriEdit := TNewEdit.Create(MongoPage);
  MongoUriEdit.Parent := MongoPage.Surface;
  MongoUriEdit.Left := 20;
  MongoUriEdit.Top := 90;
  MongoUriEdit.Width := MongoPage.SurfaceWidth - 40;
  MongoUriEdit.Text := 'mongodb+srv://user:password@cluster.mongodb.net/';

  DbNameLabel := TNewStaticText.Create(MongoPage);
  DbNameLabel.Parent := MongoPage.Surface;
  DbNameLabel.Caption := 'Database Name:';
  DbNameLabel.Left := 20;
  DbNameLabel.Top := 120;

  DbNameEdit := TNewEdit.Create(MongoPage);
  DbNameEdit.Parent := MongoPage.Surface;
  DbNameEdit.Left := 20;
  DbNameEdit.Top := 140;
  DbNameEdit.Width := MongoPage.SurfaceWidth - 40;
  DbNameEdit.Text := 'zahcci_customization';

  MongoLocalRadio := TNewRadioButton.Create(MongoPage);
  MongoLocalRadio.Parent := MongoPage.Surface;
  MongoLocalRadio.Caption := 'Install MongoDB locally (mongodb://localhost:27017)';
  MongoLocalRadio.Left := 0;
  MongoLocalRadio.Top := 180;
  MongoLocalRadio.Width := MongoPage.SurfaceWidth;
end;

function GetMongoMode: String;
begin
  if MongoLocalRadio.Checked then
    Result := 'local'
  else
    Result := 'remote';
end;

function GetMongoUri: String;
begin
  if MongoLocalRadio.Checked then
    Result := 'mongodb://localhost:27017'
  else
    Result := MongoUriEdit.Text;
end;

function GetDbName: String;
begin
  Result := DbNameEdit.Text;
end;

function MongoPageValidate: Boolean;
begin
  Result := True;
  if MongoRemoteRadio.Checked then
  begin
    if Trim(MongoUriEdit.Text) = '' then
    begin
      MsgBox('Please enter a MongoDB connection string.', mbError, MB_OK);
      Result := False;
    end
    else if Trim(DbNameEdit.Text) = '' then
    begin
      MsgBox('Please enter a database name.', mbError, MB_OK);
      Result := False;
    end;
  end;
end;

procedure MongoRemoteRadioClick(Sender: TObject);
begin
  MongoUriEdit.Enabled := MongoRemoteRadio.Checked;
  DbNameEdit.Enabled := MongoRemoteRadio.Checked;
end;

procedure BindMongoWizardEvents;
begin
  MongoRemoteRadio.OnClick := @MongoRemoteRadioClick;
  MongoLocalRadio.OnClick := @MongoRemoteRadioClick;
end;
