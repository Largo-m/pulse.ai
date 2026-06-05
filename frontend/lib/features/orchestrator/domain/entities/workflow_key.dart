final class WorkflowKey {
  const WorkflowKey._();

  static const String separator = '::';

  static String compose({required String projectId, required String slug}) {
    return '$projectId$separator$slug';
  }

  static ({String projectId, String slug})? parse(String workflowKey) {
    final int index = workflowKey.indexOf(separator);
    if (index <= 0 || index >= workflowKey.length - separator.length) {
      return null;
    }
    return (
      projectId: workflowKey.substring(0, index),
      slug: workflowKey.substring(index + separator.length),
    );
  }
}
