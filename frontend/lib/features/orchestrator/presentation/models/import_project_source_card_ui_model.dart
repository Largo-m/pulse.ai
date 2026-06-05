import 'package:flutter/material.dart';

final class ImportProjectSourceCardUiModel {
  const ImportProjectSourceCardUiModel({
    required this.badgeLabel,
    required this.title,
    required this.body,
    required this.features,
    required this.buttonLabel,
    required this.icon,
    required this.buttonTrailingIcon,
    required this.accentColor,
    required this.iconColor,
    required this.onPressed,
  });

  final String badgeLabel;
  final String title;
  final String body;
  final List<String> features;
  final String buttonLabel;
  final IconData icon;
  final IconData buttonTrailingIcon;
  final Color accentColor;
  final Color iconColor;
  final VoidCallback onPressed;
}
