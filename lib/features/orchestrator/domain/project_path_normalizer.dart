import 'package:path/path.dart' as p;

final class ProjectPathNormalizer {
  const ProjectPathNormalizer({this.basePath = '/'});

  final String basePath;

  String normalizeToAbsoluteId(String rawPath) {
    final String trimmed = rawPath.trim();
    if (trimmed.isEmpty) {
      throw ArgumentError.value(rawPath, 'rawPath', 'must not be empty');
    }

    final String normalized = p.normalize(trimmed);
    if (p.isAbsolute(normalized)) {
      return _collapseDuplicateSeparators(normalized);
    }

    final String absolute = p.normalize(p.join(basePath, normalized));
    return _collapseDuplicateSeparators(absolute);
  }

  String _collapseDuplicateSeparators(String value) {
    if (p.separator == '/') {
      return value.replaceAll(RegExp(r'/+'), '/');
    }
    return value.replaceAll(RegExp(r'\\+'), r'\');
  }
}
