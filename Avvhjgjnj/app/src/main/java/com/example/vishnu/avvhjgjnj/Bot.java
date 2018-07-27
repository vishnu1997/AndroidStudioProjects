package com.example.vishnu.avvhjgjnj;

/**
 * Created by vishnu on 4/3/16.
 */
public class Bot {
    private String creator;
    private String robot;
    public Bot(){
        creator="prabhath";
        robot = "ajshskj";
    }

    public String getCreator() {
        return creator;
    }

    public void setRobot(String robot) {
        this.robot = robot;
    }

    public String getRobot() {
        return robot;
    }

    public void setCreator(String creator) {

        this.creator = creator;
    }

    public talk(String robot){
        WriteToLog(robot);
    }
}

