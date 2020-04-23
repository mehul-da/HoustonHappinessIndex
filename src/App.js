import React from 'react';
import './App.css';
import firebase from 'firebase'

const firebaseConfig = {
  apiKey: "AIzaSyAq8EJV3ezu7zjbKxwrzuXaKZ28yYwD7x8",
  authDomain: "houston-happiness-index.firebaseapp.com",
  databaseURL: "https://houston-happiness-index.firebaseio.com",
  projectId: "houston-happiness-index",
  storageBucket: "houston-happiness-index.appspot.com",
  messagingSenderId: "18284187781",
  appId: "1:18284187781:web:eceb94efbf4f12776b59ec",
  measurementId: "G-8FKR6ME7Z9"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);

class App extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      percentage: 100.0
    }
  }

  intervalID = null;

  componentDidMount() {
      this.intervalID = setInterval(this.getAveragePercentage.bind(this), 10000);
      this.getAveragePercentage();
  }

  componentWillUnmount() {
      clearInterval(this.intervalID)
  }

  getAveragePercentage = () => {
    let totalScore = 0.0;
    let count = 0;
    const database = firebase.database();
    const info = database.ref('info');
    info.once('value').then(function(snapshot) {
      snapshot.forEach(function(childSnapshot) {
        const childData = childSnapshot.val();
        count++;
        const score = parseFloat(childData.Score) * 100;
        totalScore += score;
      });
    }).then(() => {
      const newPercentage = totalScore/count;
      const newPercentageFixed = newPercentage.toFixed(2);
      this.setState({percentage: newPercentageFixed})
    });
  }

  render() {
    return (
      <div className="App">
        <header className="App-header">
          <div style = {{marginBottom: 40, marginTop: 80}}>
          <text style = {{fontSize: 60}}>Houston Happiness Index</text>
          </div>
          <div style = {{marginBottom: 50, marginLeft: 120, marginRight: 120}}>
          <text style = {{fontSize: 20}}>Hey! This is an analysis of the sentiments of Houston area residents in
          regards to the ongoing COVID-19 pandemic. The bar below represents the happiness level of 
          Houston residents based on tweets from the region that address the lockdown, quarantine life as well as
          working/learning from home. Enjoy!</text>
          </div>
          <div style = {{marginBottom: 60}}>
          <text style = {{fontSize: 60}}>{this.state.percentage}%</text>
          </div>
          <ProgressBar percentage = {this.state.percentage}/>
        </header>
      </div>
    );
  }
}

const ProgressBar = (props) => {
  return (
    <div className = 'progress-bar'>
      <Filler percentage = {props.percentage}/>
    </div>
  )
}

const Filler = (props) => {
  return (
    <div className = 'filler' style = {{width: `${props.percentage}%`}}/>
  )
}

export default App;
