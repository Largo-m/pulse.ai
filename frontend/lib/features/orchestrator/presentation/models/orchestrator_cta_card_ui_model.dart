import 'package:flutter/material.dart';

final class OrchestratorCtaCardUiModel {
  OrchestratorCtaCardUiModel({
    required this.title,
    required this.body,
    required this.icon,
    required this.accentBorderHover,
    required this.iconColor,
    required this.buttonLabel,
    required this.usesPrimaryButtonStyle,
    required this.onPressed,
  });

  final String title;
  final String body;
  final IconData icon;
  final Color accentBorderHover;
  final Color iconColor;
  final String buttonLabel;
  final bool usesPrimaryButtonStyle;
  final VoidCallback onPressed;
}
