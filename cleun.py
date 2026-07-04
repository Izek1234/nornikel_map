unwanted_emails = {"jansonxaxaxa@users.noreply.github.com", "y9painfmeow@gmail.com"}
if commit.author_email in unwanted_emails or commit.committer_email in unwanted_emails:
    commit.author_name = "Ilfat Hismatullin"
    commit.author_email = "ilfathismatullin39@gmail.com"
    commit.committer_name = "Ilfat Hismatullin"
    commit.committer_email = "ilfathismatullin39@gmail.com"
