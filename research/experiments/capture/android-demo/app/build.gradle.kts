plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.mylittlechef.researchdemo"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.mylittlechef.researchdemo"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.androidx.camera.video)
    implementation(libs.opencv)
    testImplementation(libs.junit)
}
