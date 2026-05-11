/**
 * @jest-environment jsdom
 */

// Mock AudioContext
const mockOscillator = {
    connect: jest.fn(),
    start: jest.fn(),
    stop: jest.fn(),
    type: '',
    frequency: {
        setValueAtTime: jest.fn(),
        exponentialRampToValueAtTime: jest.fn()
    }
};

const mockGain = {
    connect: jest.fn(),
    gain: {
        setValueAtTime: jest.fn(),
        exponentialRampToValueAtTime: jest.fn()
    }
};

const mockAudioContext = {
    createOscillator: jest.fn(() => mockOscillator),
    createGain: jest.fn(() => mockGain),
    destination: {},
    currentTime: 0,
    resume: jest.fn(),
    state: 'suspended'
};

global.AudioContext = jest.fn(() => mockAudioContext);

const {
    initAudio,
    playTick,
    playGong
} = require('../static/js/audio.js');

describe('Audio Logic', () => {
    test('initAudio initializes and resumes context', () => {
        initAudio();
        expect(global.AudioContext).toHaveBeenCalled();
        expect(mockAudioContext.resume).toHaveBeenCalled();
    });

    test('playTick creates and starts oscillator', () => {
        initAudio();
        playTick();
        expect(mockAudioContext.createOscillator).toHaveBeenCalled();
        expect(mockOscillator.start).toHaveBeenCalled();
    });

    test('playGong creates and starts oscillator with ramp', () => {
        initAudio();
        playGong();
        expect(mockOscillator.frequency.exponentialRampToValueAtTime).toHaveBeenCalled();
        expect(mockOscillator.start).toHaveBeenCalled();
    });
});
