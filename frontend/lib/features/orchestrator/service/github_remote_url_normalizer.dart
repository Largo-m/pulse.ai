String? normalizeToGithubHttpsUrl(String rawUrl) {
  final String trimmed = rawUrl.trim();
  if (trimmed.isEmpty) {
    return null;
  }

  final RegExp scpStyle = RegExp(r'^git@github\.com:(.+?)(\.git)?$');
  final Match? scpMatch = scpStyle.firstMatch(trimmed);
  if (scpMatch != null) {
    final String repoPath = scpMatch
        .group(1)!
        .replaceAll(RegExp(r'^/+|/+$'), '');
    if (repoPath.isNotEmpty) {
      return 'https://github.com/$repoPath';
    }
    return null;
  }

  final Uri? uri = Uri.tryParse(trimmed);
  if (uri == null || uri.host != 'github.com') {
    return null;
  }

  String path = uri.path;
  if (path.endsWith('.git')) {
    path = path.substring(0, path.length - 4);
  }
  path = path.replaceAll(RegExp(r'^/+|/+$'), '');
  if (path.isEmpty) {
    return null;
  }

  return Uri(scheme: 'https', host: 'github.com', path: '/$path').toString();
}
