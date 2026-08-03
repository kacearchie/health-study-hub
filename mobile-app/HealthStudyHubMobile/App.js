// App.js - Health Study Hub Mobile App
import React, { useState, useEffect } from 'react';
import {
    SafeAreaView,
    StyleSheet,
    StatusBar,
    Text,
    View,
    TouchableOpacity,
    ActivityIndicator,
    Dimensions,
} from 'react-native';
import { WebView } from 'react-native-webview';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { NavigationContainer } from '@react-navigation/native';
import { createStackNavigator } from '@react-navigation/stack';

const Stack = createStackNavigator();
const { width, height } = Dimensions.get('window');

// ============================================================
// SPLASH SCREEN
// ============================================================
const SplashScreen = ({ navigation }) => {
    useEffect(() => {
        setTimeout(() => {
            navigation.replace('Main');
        }, 2000);
    }, []);

    return (
        <View style={styles.splashContainer}>
            <View style={styles.splashContent}>
                <Text style={styles.splashLogo}>🏥</Text>
                <Text style={styles.splashTitle}>Health Study Hub</Text>
                <Text style={styles.splashSubtitle}>Pharmaceutical & Health Sciences</Text>
                <View style={styles.splashProgressContainer}>
                    <View style={[styles.splashProgressBar, { width: '70%' }]} />
                </View>
                <Text style={styles.splashVersion}>MUST / UG</Text>
            </View>
        </View>
    );
};

// ============================================================
// MAIN APP
// ============================================================
const MainApp = () => {
    const [serverUrl, setServerUrl] = useState('');
    const [loading, setLoading] = useState(true);
    const [isOffline, setIsOffline] = useState(false);

    useEffect(() => {
        checkConnection();
    }, []);

    const checkConnection = async () => {
        // Try multiple URLs
        const urls = [
    'https://health-study-hub.onrender.com', // <- Your Render URL
    'http://192.168.1.100:5000',
];
        let connected = false;
        for (const url of urls) {
            try {
                const response = await fetch(`${url}/health`, {
                    method: 'GET',
                    headers: { 'Content-Type': 'application/json' },
                });
                if (response.ok) {
                    setServerUrl(url);
                    connected = true;
                    break;
                }
            } catch (e) {
                console.log('Server not available:', url);
            }
        }

        if (!connected) {
            // Check if we have offline content
            try {
                const offlineContent = await AsyncStorage.getItem('offlineData');
                if (offlineContent) {
                    setIsOffline(true);
                } else {
                    setIsOffline(true);
                }
            } catch (e) {
                setIsOffline(true);
            }
        }
        setLoading(false);
    };

    if (loading) {
        return (
            <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#2563eb" />
                <Text style={styles.loadingText}>Connecting...</Text>
            </View>
        );
    }

    if (isOffline && !serverUrl) {
        return (
            <View style={styles.offlineContainer}>
                <Text style={styles.offlineIcon}>📶</Text>
                <Text style={styles.offlineTitle}>Offline Mode</Text>
                <Text style={styles.offlineText}>
                    Please connect to the internet to access the app.
                </Text>
                <TouchableOpacity
                    style={styles.retryButton}
                    onPress={checkConnection}
                >
                    <Text style={styles.retryButtonText}>🔄 Retry</Text>
                </TouchableOpacity>
            </View>
        );
    }

    return (
        <SafeAreaView style={styles.container}>
            <StatusBar barStyle="light-content" backgroundColor="#2563eb" />
            <WebView
                source={{ uri: serverUrl }}
                style={styles.webview}
                cacheEnabled={true}
                javaScriptEnabled={true}
                domStorageEnabled={true}
                startInLoadingState={true}
                renderLoading={() => (
                    <View style={styles.loadingContainer}>
                        <ActivityIndicator size="large" color="#2563eb" />
                        <Text style={styles.loadingText}>Loading...</Text>
                    </View>
                )}
                onError={() => {
                    setIsOffline(true);
                }}
            />
        </SafeAreaView>
    );
};

// ============================================================
// APP NAVIGATION
// ============================================================
const App = () => {
    return (
        <NavigationContainer>
            <Stack.Navigator screenOptions={{ headerShown: false }}>
                <Stack.Screen name="Splash" component={SplashScreen} />
                <Stack.Screen name="Main" component={MainApp} />
            </Stack.Navigator>
        </NavigationContainer>
    );
};

// ============================================================
// STYLES
// ============================================================
const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#f8fafc',
    },
    webview: {
        flex: 1,
    },
    splashContainer: {
        flex: 1,
        backgroundColor: '#2563eb',
        justifyContent: 'center',
        alignItems: 'center',
    },
    splashContent: {
        alignItems: 'center',
        paddingHorizontal: 30,
    },
    splashLogo: {
        fontSize: 80,
        marginBottom: 15,
    },
    splashTitle: {
        fontSize: 32,
        fontWeight: 'bold',
        color: 'white',
        marginBottom: 5,
    },
    splashSubtitle: {
        fontSize: 16,
        color: 'rgba(255,255,255,0.8)',
        marginBottom: 20,
    },
    splashProgressContainer: {
        width: 200,
        height: 4,
        backgroundColor: 'rgba(255,255,255,0.3)',
        borderRadius: 2,
        overflow: 'hidden',
        marginBottom: 10,
    },
    splashProgressBar: {
        height: '100%',
        backgroundColor: 'white',
        borderRadius: 2,
    },
    splashVersion: {
        fontSize: 12,
        color: 'rgba(255,255,255,0.6)',
    },
    loadingContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#f8fafc',
    },
    loadingText: {
        marginTop: 10,
        fontSize: 14,
        color: '#475569',
    },
    offlineContainer: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        padding: 20,
        backgroundColor: '#f8fafc',
    },
    offlineIcon: {
        fontSize: 60,
        marginBottom: 15,
    },
    offlineTitle: {
        fontSize: 22,
        fontWeight: 'bold',
        color: '#0f172a',
        marginBottom: 10,
    },
    offlineText: {
        fontSize: 14,
        color: '#475569',
        textAlign: 'center',
        marginBottom: 20,
    },
    retryButton: {
        backgroundColor: '#2563eb',
        paddingHorizontal: 30,
        paddingVertical: 12,
        borderRadius: 8,
    },
    retryButtonText: {
        color: 'white',
        fontSize: 16,
        fontWeight: '600',
    },
});

export default App;