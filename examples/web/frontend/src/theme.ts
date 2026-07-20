import { createTheme, type MantineColorsTuple } from "@mantine/core";

const gold: MantineColorsTuple = [
  "#fdf7e6", "#f8ecc4", "#f2dfa0", "#ecd27a", "#e7c657",
  "#e2ba3e", "#d4a33a", "#c9a83a", "#a3862e", "#7d6423",
];

// Overrides Mantine's built-in "dark" palette so every component that uses
// the default dark-scheme surfaces (AppShell, Paper, Card, Modal, ...)
// picks up this app's navy palette automatically. Mantine's dark-scheme
// convention: shade 7 is the body background, shade 6 is the Paper/Card
// surface — indices chosen so those two land on the approved mockup's
// exact colors.
const dark: MantineColorsTuple = [
  "#d3d3e6", "#a7a7cb", "#8181af", "#606093", "#454577",
  "#2a2b45", "#1e1f38", "#14152a", "#101124", "#0b0c1c",
];

export const theme = createTheme({
  primaryColor: "gold",
  primaryShade: 6,
  colors: { gold, dark },
  defaultRadius: "md",
});
