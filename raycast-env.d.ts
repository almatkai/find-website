/// <reference types="@raycast/api">

/* 🚧 🚧 🚧
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 * 🚧 🚧 🚧 */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Browser - Select your browser */
  "browser": "chrome" | "orion" | "arc" | "safari" | "firefox" | "zen" | "brave" | "vivaldi" | "opera" | "edge",
  /** Profile Directory - (Google Chrome only) Directory where your profile's data is saved. */
  "profile": string
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `find` command */
  export type Find = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `find` command */
  export type Find = {}
}

