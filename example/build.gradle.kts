plugins { kotlin("multiplatform") version "2.4.21" }

kotlin {
    linuxArm64 { binaries.executable { baseName = "entry"; entryPoint = "ink.example.main" } }
    linuxX64 { binaries.executable { baseName = "entry"; entryPoint = "ink.example.main" } }
    applyDefaultHierarchyTemplate()
}
