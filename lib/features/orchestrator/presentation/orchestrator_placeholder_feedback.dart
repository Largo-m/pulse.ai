import 'package:flutter/material.dart';

abstract final class OrchestratorPlaceholderFeedback {
  static void showComingSoon(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Em breve: integração ainda não disponível.'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
